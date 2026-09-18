#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
root="$PWD"
rocm="${ROCM_PATH:-/opt/rocm}"
arch="${MINUTORY_HIP_ARCH:-gfx1100}"
jobs="${MINUTORY_BUILD_JOBS:-6}"
source_dir="$root/cache/build/ctranslate2"
install_dir="$root/libs/ctranslate2-hip"
[[ -x .venv/bin/python ]] || { echo 'Run bootstrap.sh first.'; exit 1; }
for tool in git cmake ninja uv; do command -v "$tool" >/dev/null || { echo "Missing $tool"; exit 1; }; done
[[ -x "$rocm/lib/llvm/bin/clang++" ]] || { echo "Missing ROCm compiler under $rocm"; exit 1; }
export ROCM_PATH="$rocm"
export LD_LIBRARY_PATH="$install_dir/lib:$install_dir/lib64:$rocm/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
if [[ ! -d "$source_dir/.git" ]]; then
    mkdir -p "$root/cache/build"
    git clone --recursive --depth 1 --branch v4.8.2 https://github.com/OpenNMT/CTranslate2.git "$source_dir"
fi
# Pin the release commit rather than building whichever checkout is present.
git -C "$source_dir" checkout --detach d44d2d069eb88c7b7804da864c10c201501cb4a9
git -C "$source_dir" submodule update --init --recursive
cmake -S "$source_dir" -B "$source_dir/build-hip" -G Ninja \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$install_dir" -DCMAKE_INSTALL_LIBDIR=lib \
    -DCMAKE_PREFIX_PATH="$rocm" -DCMAKE_HIP_COMPILER="$rocm/lib/llvm/bin/clang++" \
    -DCMAKE_C_COMPILER="$rocm/lib/llvm/bin/clang" -DCMAKE_CXX_COMPILER="$rocm/lib/llvm/bin/clang++" -DCMAKE_HIP_ARCHITECTURES="$arch" \
    -DWITH_HIP=ON -DWITH_CUDA=OFF -DWITH_MKL=OFF -DWITH_RUY=ON \
    -DOPENMP_RUNTIME=COMP -DBUILD_CLI=OFF -DBUILD_TESTS=OFF
cmake --build "$source_dir/build-hip" --parallel "$jobs"
cmake --install "$source_dir/build-hip"
uv pip install --python .venv/bin/python -r "$source_dir/python/install_requirements.txt"
(
    cd "$source_dir/python"
    CTRANSLATE2_ROOT="$install_dir" CMAKE_BUILD_PARALLEL_LEVEL="$jobs" \
        "$root/.venv/bin/python" setup.py bdist_wheel
)
uv pip install --python .venv/bin/python --reinstall --no-deps "$source_dir"/python/dist/ctranslate2-4.8.2-*.whl
.venv/bin/python - <<'PY'
import ctranslate2
count = ctranslate2.get_cuda_device_count()
types = ctranslate2.get_supported_compute_types('cuda')
if count < 1 or 'float16' not in types:
    raise SystemExit('HIP verification failed: no usable float16 GPU.')
print(f'HIP build ready: {count} AMD device(s); compute types: {sorted(types)}')
PY
# Update only the two ASR settings, preserving credentials and all other settings.
.venv/bin/python - <<'PY'
from pathlib import Path
path = Path('.env')
if not path.exists():
    path.write_text(Path('.env.linux.example').read_text())
lines = path.read_text().splitlines()
for key, value in [('MINUTORY_ASR_DEVICE', 'cuda'), ('MINUTORY_ASR_COMPUTE_TYPE', 'float16')]:
    lines = [line for line in lines if not line.strip().startswith(key + '=')]
    lines.append(f'{key}={value}')
path.write_text('\n'.join(lines) + '\n')
PY
