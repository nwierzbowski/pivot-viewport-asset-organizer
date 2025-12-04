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

To compile the .pyd/.so files from the source code, follow these steps:

1. Install dependencies using uv:
   ```
   uv sync
   ```
   After running `uv sync`, activate the virtual environment for your operating system:
   - On Windows: `.venv\Scripts\activate`
   - On macOS/Linux: `source .venv/bin/activate`

2. For the Pro edition build:
   ```
   cmake --preset=pro
   ninja -C build-pro
   ```

3. For the Standard edition build:
   ```
   cmake --preset=standard
   ninja -C build-standard
   ```

The builds use the Ninja generator and output the binaries and Cython modules into the repository's `pivot/` folder. After building, zip the `pivot/` folder and install it as a Blender addon.
