# 3D Tiles to KMZ (DJI Terra)

Convert a DJI Terra **3D Tiles** export (`tileset.json` + `.b3dm`) into a Google Earth **KMZ** with a COLLADA `.dae` model.
KMZ model can be uploaded to UgCS. 

## 1) Set up a Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

## 2) Install dependencies (Python + non-Python)

Use the provided installer script. It sets up Python deps and installs required non-Python tools.

```bash
./install_deps.sh
```

## 3) Run the converter

```bash
python3 3dtiles2kmz.py --input /path/to/tileset_dir --output /path/to/output.kmz
```

Notes:
- The input directory must contain `tileset.json`.
- The output path must end with `.kmz`.

## Known Issues/Future plans
- There is now mesh optimization. Script takes the most detailed level of 3D tile octree, so resulting KMZ file can be huge
- No textures support, so far

## License
Apache License 2.0. See `LICENSE`.
