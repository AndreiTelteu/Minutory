from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def verify_runtime(ffmpeg: Path, ffprobe: Path, *, require_windows_gpu: bool = True) -> tuple[Check, ...]:
    checks = [
        Check(
            "Python",
            sys.version_info[:2] == (3, 12) and platform.architecture()[0] == "64bit",
            f"{platform.python_version()} · {platform.architecture()[0]}",
        )
    ]
    for name, command in (("FFmpeg", ffmpeg), ("FFprobe", ffprobe)):
        executable = shutil.which(str(command)) or (str(command) if command.is_file() else None)
        if executable is None:
            checks.append(Check(name, False, f"{command} was not found. Re-run bootstrap."))
            continue
        result = subprocess.run(
            [executable, "-version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        first_line = (result.stdout or result.stderr).splitlines()
        checks.append(
            Check(name, result.returncode == 0, first_line[0] if first_line else "No version output.")
        )
    try:
        import ctranslate2

        version_ok = ctranslate2.__version__ == "4.8.1"
        checks.append(Check("CTranslate2", version_ok, f"version {ctranslate2.__version__} (ROCm required)"))
        package_root = Path(ctranslate2.__file__).resolve().parent
        hip_libraries = list(package_root.parent.rglob("amdhip64*.dll"))
        checks.append(
            Check(
                "CTranslate2 ROCm backend",
                bool(hip_libraries),
                "AMD HIP runtime library detected."
                if hip_libraries
                else (
                    "AMD HIP runtime library was not found beside CTranslate2. "
                    "The stock CUDA wheel may be installed."
                ),
            )
        )
        device_count = int(ctranslate2.get_cuda_device_count())
        checks.append(
            Check(
                "HIP device",
                device_count > 0,
                f"{device_count} CTranslate2 CUDA/HIP device(s) visible."
                if device_count
                else (
                    "No HIP device is visible. Install AMD Adrenalin/ROCm runtime and verify the ROCm wheel."
                ),
            )
        )
    except Exception as exception:
        checks.append(
            Check(
                "CTranslate2",
                False,
                f"{exception}. Install the official ROCm/HIP 4.8.1 wheel; "
                "do not install stock CUDA CTranslate2.",
            )
        )
    if sys.platform == "win32":
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "(Get-CimInstance Win32_VideoController).Name",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        names = result.stdout.strip()
        checks.append(
            Check(
                "RX 7900 XTX",
                "7900 XTX" in names.upper(),
                names or "Windows did not report a video controller.",
            )
        )
    elif require_windows_gpu:
        checks.append(Check("RX 7900 XTX", False, "Hardware verification must run on Windows 11."))
    model = Path(__file__).resolve().parents[2] / "models/large-v3"
    model_files = (
        "model.bin",
        "config.json",
        "tokenizer.json",
        "vocabulary.json",
        "preprocessor_config.json",
    )
    missing = [name for name in model_files if not (model / name).is_file()]
    checks.append(
        Check(
            "Large v3 model",
            not missing,
            "Complete local model snapshot detected."
            if not missing
            else f"Missing {', '.join(missing)} under {model}. Re-run bootstrap.",
        )
    )
    return tuple(checks)


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    checks = verify_runtime(
        root / "libs/ffmpeg/bin/ffmpeg.exe",
        root / "libs/ffmpeg/bin/ffprobe.exe",
    )
    for check in checks:
        print(f"{'OK' if check.ok else 'ERROR'}  {check.name}: {check.detail}")
    return 0 if all(check.ok for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
