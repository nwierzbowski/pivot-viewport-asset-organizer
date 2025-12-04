# PIVOT BRIDGE - GPL COMPLIANT SOURCE CODE

This repository contains the full source code for the GPLv3-licensed Python and Cython bridge components of the Pivot addon for Blender.

This code is provided in full compliance with the GNU General Public License (GPL) and is distributed to ensure users have the freedom to study, modify, and redistribute the open-source components of our product.

## Licensing
*   **Bridge Code:** Licensed under the GNU General Public License v3.0 or any later version. See [License](https://github.com/nwierzbowski/pivot-blender-bridge/blob/main/LICENSE) for the full text.
*   **Proprietary Engine:** The bridge component is designed to communicate with a separate, proprietary C++ application, the "Elbo Core Engine." The source code for the Engine is not included here.
*   **The Full Product:** The full, installable addon and the proprietary engine can be acquired from [Gumroad](https://gumroad.com) or [Superhive](https://superhivemarket.com/products/pivot). Standard edition is free on Gumroad and $5 on Superhive, while Pro edition is $30 on both platforms. More information is available at [elbo.studio](https://www.elbo.studio).

## Purpose
The sole purpose of this code is to serve as a user interface and a high-speed data marshalling layer between the Blender Python API and the external Elbo Core Engine.

## Setup/Compilation

To compile the .pyd/.so files from the source code, you must first install the necessary development dependencies using uv.

**Prerequisites:** You must have the 'uv' package manager installed on your system.

1. Clone the repository recursively and enter the directory:
```
git clone --recursive https://github.com/nwierzbowski/pivot-blender-bridge.git
cd pivot-blender-bridge
```

2. **Initialize the Development Environment:**
This step creates a self-contained Python Virtual Environment (`.venv`) and installs the exact versions of 'cmake', 'cython', 'numpy', and 'ninja' needed to compile the bridge code.
   ```
   uv sync
   ```
   After running `uv sync`, activate the virtual environment for your operating system:
   - On Windows: `.venv\Scripts\activate`
   - On macOS/Linux: `source .venv/bin/activate`

3. **Compile the Bridge Binary:**
(Once the environment is active, the following commands will run your build system)

For the Pro edition build:
   ```
   cmake --preset=pro
   ninja -C build-pro
   ```

For the Standard edition build:
   ```
   cmake --preset=standard
   ninja -C build-standard
   ```

The builds use the Ninja generator and output the binaries and Cython modules into the repository's `pivot/` folder. Specifically, the compiled .so (Linux/macOS) or .pyd (Windows) binaries will be placed in `pivot/lib/your-architecture/` (e.g., `pivot/lib/linux-x86-64/`). An empty `bin/` folder will also be present in the `pivot/` directory, where the compiled proprietary Elbo Core Engine binary must be manually placed after acquisition from the official sources. Note that this build process does not generate the proprietary engine, as its source code is not included in this repository due to its proprietary nature.

After building, zip the `pivot/` folder and install it as a Blender addon.
