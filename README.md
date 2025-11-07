````markdown
# Pivot Build Workflow

The build system targets the Blender add-on directly. All binaries and Cython modules are emitted into the repository's `pivot/` folder so the add-on can be zipped or installed without extra staging steps. Builds use the Ninja generator.

## Default (Pro) build

```
cmake --preset=default
ninja -C build
```

Outputs:

- Engine executable: `pivot/bin/pivot_engine`
- Cython modules: `pivot/lib/*.so`

The configure preset defaults to the **Pro** edition and sets the compile definitions `PIVOT_EDITION_PRO=1` and `PIVOT_EDITION_STANDARD=0`.

## Standard edition build

```
cmake --preset=standard
ninja -C build-standard
```

This preset switches the edition to **Standard**, flipping the compile definitions accordingly. Each preset maintains its own build directory so you can generate both editions without a clean rebuild.

If you prefer to toggle the edition manually, set the cache variable when configuring:

```
cmake -S . -B build -DPIVOT_EDITION=STANDARD
```

After configuring, run `ninja -C <build-dir>` to rebuild.

````
