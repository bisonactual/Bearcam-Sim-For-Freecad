# The viewer program: found in the local folder the user chose, else downloaded once per platform
# from the release and checked against the SHA-256 pinned in release.json, then started as its own
# process, silently. A job whose viewer is still open is only re-posted: the viewer sees its files
# change and reads them again.
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile

from .jobmap import SimError

HERE = os.path.dirname(os.path.abspath(__file__))


def release():
    with open(os.path.join(HERE, "release.json"), encoding="utf-8") as f:
        return json.load(f)


def platform_key():
    if sys.platform.startswith("win"):
        name = "windows"
    elif sys.platform.startswith("linux"):
        name = "linux"
    elif sys.platform == "darwin":
        raise SimError("The BearCAM simulator does not run on macOS for now (it needs OpenGL 4.5 or 4.6).")
    else:
        raise SimError(f"The BearCAM simulator has no build for {sys.platform}.")
    machine = platform.machine().lower()
    if machine not in ("amd64", "x86_64"):
        raise SimError(f"The BearCAM simulator has no build for {machine} processors yet (x86-64 only).")
    return name + "-x86_64"


def exe_name():
    return "stockviewer.exe" if sys.platform.startswith("win") else "stockviewer"


def cache_dir(user_data_dir):
    rel = release()
    return os.path.join(user_data_dir, "BearCAMSimulator", rel["version"], platform_key())


def in_folder(folder):
    """The viewer in a folder or one folder down (an unpacked release keeps its files under
    bearcam-simulator-VERSION/), or None."""
    exe = os.path.join(folder, exe_name())
    if os.path.isfile(exe):
        return exe
    try:
        subs = sorted(os.listdir(folder))
    except OSError:
        return None
    for sub in subs:
        exe = os.path.join(folder, sub, exe_name())
        if os.path.isfile(exe):
            return exe
    return None


def find(local_folder, user_data_dir):
    """The viewer to run: the local folder's (a setting, for testing before anything is
    published), else the downloaded and checked release. None: not downloaded yet."""
    if local_folder:
        exe = in_folder(local_folder)
        if not exe:
            raise SimError(f"There is no {exe_name()} in the local viewer folder {local_folder}.")
        return exe
    folder = cache_dir(user_data_dir)
    exe = in_folder(folder)
    if exe and os.path.isfile(os.path.join(folder, ".checked")):
        return exe
    return None


def download_info():
    """(url, file name, size in bytes or None) of this platform's release, or None when nothing is
    published yet."""
    rel = release()
    entry = rel.get("files", {}).get(platform_key())
    if not rel.get("base_url") or not entry or not entry.get("sha256"):
        return None
    return rel["base_url"].rstrip("/") + "/" + entry["name"], entry["name"], entry.get("size")


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# An unpacked release is about 2 MB; anything past this is not one.
MAX_UNPACKED = 200 << 20


def safe_members(names, dest):
    root = os.path.realpath(dest)
    for n in names:
        target = os.path.realpath(os.path.join(dest, n))
        if not (target == root or target.startswith(root + os.sep)):
            raise SimError(f"The download holds a file outside its folder ({n}); it was not unpacked.")


def check_tar(t, dest):
    """Only plain files and folders inside dest, at most MAX_UNPACKED in all: no links (a link's
    target is not checked by its name), devices or pipes."""
    members = t.getmembers()
    safe_members([m.name for m in members], dest)
    for m in members:
        if not (m.isfile() or m.isdir()):
            raise SimError(f"The download holds {m.name}, which is not a plain file or folder; it was not unpacked.")
    if sum(m.size for m in members if m.isfile()) > MAX_UNPACKED:
        raise SimError("The download unpacks to more than 200 MB; it was not unpacked.")


def check_zip(z, dest):
    """As check_tar: names inside dest, no symbolic links, at most MAX_UNPACKED in all."""
    infos = z.infolist()
    safe_members([i.filename for i in infos], dest)
    for i in infos:
        if (i.external_attr >> 16) & 0o170000 == 0o120000:
            raise SimError(f"The download holds a link ({i.filename}); it was not unpacked.")
    if sum(i.file_size for i in infos) > MAX_UNPACKED:
        raise SimError("The download unpacks to more than 200 MB; it was not unpacked.")


class HttpsOnly(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to another https:// address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith("https://"):
            raise SimError(f"The download was redirected to {newurl}, which is not HTTPS; it was stopped.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(user_data_dir, progress=None):
    """Downloads this platform's viewer, checks it against the pinned SHA-256, unpacks it into
    the cache and returns the viewer's path."""
    info = download_info()
    if info is None:
        raise SimError("No viewer has been published for download yet: set a local viewer folder instead.")
    url, name, size = info
    if not url.lower().startswith("https://"):
        raise SimError(f"The viewer's address {url} is not HTTPS; nothing was downloaded.")
    pinned = release()["files"][platform_key()]["sha256"].lower()
    most = int(size) if size else MAX_UNPACKED  # the pinned size: more is not the pinned file
    folder = cache_dir(user_data_dir)
    os.makedirs(folder, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bearcam-sim-dl-") as tmp:
        archive = os.path.join(tmp, name)
        try:
            opener = urllib.request.build_opener(HttpsOnly)
            with opener.open(url, timeout=60) as r, open(archive, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done = 0
                while True:
                    block = r.read(1 << 16)
                    if not block:
                        break
                    done += len(block)
                    if done > most:
                        raise SimError(f"The download is larger than the pinned {most} bytes; it was stopped and not used.")
                    f.write(block)
                    if progress:
                        progress(done, total)
        except OSError as e:
            raise SimError(f"The viewer could not be downloaded from {url}: {e}") from e
        got = sha256_of(archive)
        if got != pinned:
            raise SimError(f"The downloaded viewer does not match its pinned SHA-256 (got {got}, expected {pinned}); "
                           "it was not used.")
        unpack = os.path.join(tmp, "unpacked")
        if name.endswith(".zip"):
            with zipfile.ZipFile(archive) as z:
                check_zip(z, unpack)
                z.extractall(unpack)
        else:
            with tarfile.open(archive) as t:
                check_tar(t, unpack)
                if hasattr(tarfile, "data_filter"):  # Python 3.12, and 3.8.17+ / 3.11.4+
                    t.extractall(unpack, filter="data")
                else:
                    t.extractall(unpack)
        shutil.rmtree(folder, ignore_errors=True)
        shutil.copytree(unpack, folder)
    exe = in_folder(folder)
    if not exe:
        raise SimError(f"The downloaded viewer has no {exe_name()}.")
    if not sys.platform.startswith("win"):
        os.chmod(exe, 0o755)
    with open(os.path.join(folder, ".checked"), "w", encoding="utf-8") as f:
        f.write(pinned + "\n")
    return exe


# ---- Running viewers


def process_alive(pid):
    """Whether a stockviewer process with this id is running."""
    if not pid:
        return False
    if sys.platform.startswith("win"):
        import ctypes
        from ctypes import wintypes

        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = wintypes.HANDLE
        h = k32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = wintypes.DWORD()
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != 259:  # STILL_ACTIVE
                return False
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value).lower().startswith("stockviewer")
            return True
        finally:
            k32.CloseHandle(h)
    try:
        os.kill(int(pid), 0)
        return "stockviewer" in os.path.basename(os.readlink(f"/proc/{int(pid)}/exe"))
    except OSError:
        return False


def running_pid(folder):
    try:
        with open(os.path.join(folder, "viewer.pid"), encoding="utf-8") as f:
            pid = int(f.read().strip() or 0)
    except (OSError, ValueError):
        return 0
    return pid if process_alive(pid) else 0


def launch(exe, job_path):
    """Opens the job in the viewer unless its viewer is still open (which reads the re-posted
    files by itself). Returns (pid, whether it was started now)."""
    folder = os.path.dirname(job_path)
    pid = running_pid(folder)
    if pid:
        return pid, False
    log = open(os.path.join(folder, "viewer.log"), "w", encoding="utf-8")
    kwargs = {"cwd": os.path.dirname(exe), "stdin": subprocess.DEVNULL, "stdout": log, "stderr": subprocess.STDOUT,
              "close_fds": True}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = 0x08000000 | 0x00000200  # CREATE_NO_WINDOW, CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    try:
        p = subprocess.Popen([exe, job_path], **kwargs)
    except OSError as e:
        raise SimError(f"The viewer could not be started ({exe}): {e}") from e
    finally:
        log.close()
    with open(os.path.join(folder, "viewer.pid"), "w", encoding="utf-8") as f:
        f.write(str(p.pid))
    return p.pid, True
