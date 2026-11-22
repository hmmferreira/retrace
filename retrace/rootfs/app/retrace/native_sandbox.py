"""Fail-closed Linux worker restrictions. No privileges or network namespaces."""
import ctypes
import errno
import os
from pathlib import Path
import platform
import resource
import re

class SandboxUnavailable(RuntimeError):pass

# Landlock syscall numbers are identical on our explicit supported architectures.
_CREATE_RULESET,_ADD_RULE,_RESTRICT_SELF=444,445,446
_READ_FILE,_READ_DIR=4,8
_HANDLED_FS=(1<<15)-1  # ABI 3: EXECUTE through TRUNCATE, including REFER.

class _Ruleset(ctypes.Structure):
    _fields_=[("handled_access_fs",ctypes.c_uint64)]
class _PathRule(ctypes.Structure):
    _pack_=1
    _fields_=[("allowed_access",ctypes.c_uint64),("parent_fd",ctypes.c_int32)]


def _restrict_apparmor(libc):
    """Enter a loaded nested profile permanently, before no_new_privs is set.

    No dynamic profile is loaded here and no caller-supplied name is accepted.
    Supervisor owns the enforced profile definition; the child has no transition
    rule back to its parent and cannot write its AppArmor attribute afterwards.
    """
    try:apparmor=ctypes.CDLL("libapparmor.so.1",use_errno=True)
    except OSError:raise SandboxUnavailable("worker_apparmor_unavailable") from None
    apparmor.aa_getcon.argtypes=[ctypes.POINTER(ctypes.c_char_p),ctypes.POINTER(ctypes.c_char_p)]
    apparmor.aa_getcon.restype=ctypes.c_int
    apparmor.aa_change_profile.argtypes=[ctypes.c_char_p]
    apparmor.aa_change_profile.restype=ctypes.c_int
    libc.free.argtypes=[ctypes.c_void_p]
    def context():
        label=ctypes.c_char_p();mode=ctypes.c_char_p()
        try:
            if apparmor.aa_getcon(ctypes.byref(label),ctypes.byref(mode))<0:
                raise SandboxUnavailable("worker_apparmor_profile_invalid")
            name=label.value.decode("ascii") if label.value else ""
            state=mode.value.decode("ascii") if mode.value else ""
            return name,state
        except UnicodeError:raise SandboxUnavailable("worker_apparmor_profile_invalid") from None
        finally:
            if label:libc.free(label)
    before,state=context()
    if state!="enforce" or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,254}",before):
        raise SandboxUnavailable("worker_apparmor_profile_invalid")
    target=before+"//retrace-native"
    if apparmor.aa_change_profile(target.encode("ascii"))!=0:
        raise SandboxUnavailable("worker_apparmor_transition_failed")
    after,state=context()
    if after!=target or state!="enforce":
        raise SandboxUnavailable("worker_apparmor_profile_invalid")

def restrict_worker(public_paths):
    """Must run before importing or loading any third-party/native implementation.

    Read-only paths contain public interpreter/dependency/app code, never a data
    directory. All handled writes, file execution and other reads remain denied.
    Inherited file descriptors must already be restricted by the launcher.
    """
    if platform.system()!="Linux" or platform.machine() not in ("x86_64","aarch64"):
        raise SandboxUnavailable("worker_platform_unsupported")
    libc=ctypes.CDLL(None,use_errno=True)
    # Load the trusted system filter library before the file boundary is active.
    try:seccomp=ctypes.CDLL("libseccomp.so.2",use_errno=True)
    except OSError:raise SandboxUnavailable("worker_seccomp_unavailable") from None
    libc.syscall.restype=ctypes.c_long
    landlock=libc.syscall(_CREATE_RULESET,0,0,1)>=3
    if not landlock:_restrict_apparmor(libc)
    # AppArmor profile transition must precede no_new_privs; after transition,
    # setting it plus the syscall filter makes the selected boundary permanent.
    if libc.prctl(38,1,0,0,0)!=0 or libc.prctl(4,0,0,0,0)!=0:
        raise SandboxUnavailable("worker_privilege_restriction_failed")
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
    resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
    resource.setrlimit(resource.RLIMIT_CPU,(30,30))
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    if landlock:
        attr=_Ruleset(_HANDLED_FS)
        ruleset=libc.syscall(_CREATE_RULESET,ctypes.byref(attr),ctypes.sizeof(attr),0)
        if ruleset<0:raise SandboxUnavailable("worker_landlock_unavailable")
        try:
            for raw in sorted(set(map(str,public_paths))):
                path=Path(raw)
                if not path.exists():continue
                # Resolve before applying restrictions so symlinks cannot broaden
                # rules at request time. These paths are chosen by trusted code only.
                path=path.resolve(strict=True)
                fd=os.open(path,os.O_PATH|os.O_CLOEXEC)
                try:
                    access=_READ_FILE|_READ_DIR if path.is_dir() else _READ_FILE
                    rule=_PathRule(access,fd)
                    if libc.syscall(_ADD_RULE,ruleset,1,ctypes.byref(rule),0)!=0:
                        raise SandboxUnavailable("worker_landlock_rule_failed")
                finally:os.close(fd)
            if libc.syscall(_RESTRICT_SELF,ruleset,0)!=0:
                raise SandboxUnavailable("worker_landlock_restriction_failed")
        finally:os.close(ruleset)
    seccomp.seccomp_init.argtypes=[ctypes.c_uint32];seccomp.seccomp_init.restype=ctypes.c_void_p
    seccomp.seccomp_syscall_resolve_name.argtypes=[ctypes.c_char_p];seccomp.seccomp_syscall_resolve_name.restype=ctypes.c_int
    seccomp.seccomp_rule_add.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.c_int,ctypes.c_uint]
    seccomp.seccomp_load.argtypes=[ctypes.c_void_p]
    seccomp.seccomp_release.argtypes=[ctypes.c_void_p]
    context=seccomp.seccomp_init(0x7fff0000)
    if not context:raise SandboxUnavailable("worker_seccomp_unavailable")
    try:
        denied=("socket","socketpair","connect","bind","listen","accept","accept4", "sendto","sendmsg","sendmmsg",
            "recvfrom","recvmsg","recvmmsg","execve","execveat","fork","vfork","clone","clone3",
            "ptrace","process_vm_readv","process_vm_writev","pidfd_getfd","kcmp","open_by_handle_at",
            "io_uring_setup","io_uring_enter","io_uring_register","mount","umount2","pivot_root","chroot",
            "unshare","setns","bpf","perf_event_open","keyctl","add_key","request_key","kill","tkill","tgkill",
            "pidfd_send_signal","prlimit64","setrlimit","setuid","setgid","setreuid","setregid",
            "setresuid","setresgid","setfsuid","setfsgid","setgroups","capset","personality","prctl",
            # Landlock does not mediate all inode metadata mutations. Block those
            # explicitly so same-UID native code cannot damage parent private files.
            "chmod","fchmod","fchmodat","fchmodat2","chown","fchown","lchown","fchownat",
            "utime","utimes","futimesat","utimensat","setxattr","lsetxattr","fsetxattr",
            "removexattr","lremovexattr","fremovexattr","fcntl","fcntl64","ioctl")
        critical={"socket","connect","execve","clone","ptrace","prctl","process_vm_readv",
            "process_vm_writev","io_uring_setup","kill","setns","unshare"}
        for name in denied:
            number=seccomp.seccomp_syscall_resolve_name(name.encode("ascii"))
            if number<0 and name in critical:raise SandboxUnavailable("worker_seccomp_syscall_unavailable")
            if number<0:continue  # architecture-specific absent calls have no route.
            if seccomp.seccomp_rule_add(context,0x50000|errno.EPERM,number,0)!=0:
                raise SandboxUnavailable("worker_seccomp_rule_failed")
        if seccomp.seccomp_load(context)!=0:
            raise SandboxUnavailable("worker_seccomp_restriction_failed")
    finally:seccomp.seccomp_release(context)
    return "landlock3-seccomp-v1" if landlock else "apparmor-seccomp-v1"
