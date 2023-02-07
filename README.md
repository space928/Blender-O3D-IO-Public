# Blender-O3D-IO
A plugin supporting blender 2.79-3.x for importing and exporting OMSI .sco, .cfg, and .o3d files.

![Blender-O3D-IO-Screenshot](https://user-images.githubusercontent.com/15130114/208222029-5f9c2eb7-1007-4c38-a06a-0f3214d0a2f6.png)

## Features
Currently, importing models is well-supported, exporting is currently work in progress.

### Importer
 - Fully supports O3D file format:
    - Explicit vertex normals
    - Long headers (version >= 3)
    - Encryption (automatically decrypts regardless of encryption key)
    - Long triangle indices
    - Alternative encryption seed
    - Embedded materials
    - Bones
    - UV coordinates
 - Supports many features in CFG/SCO files:
    - Imports advanced material features including:
       - `[matl]`
       - `[matl_alpha]`
       - `[matl_transmap]`
       - `[matl_envmap]`
       - ...
    - Imports all referenced models (o3d files only) and textures in the CFG/SCO as separate objects
    - Imports `.x` if a compatible importer is installed (https://github.com/Poikilos/io_import_x)

### Exporter
In its current state, the exporter doesn't work.  
 - Supports many O3D features:
    - Explicit vertex normals
    - Long headers (version >= 3)
    - Encryption [Coming soon]
    - Long triangle indices
    - Alternative encryption seed [Coming soon]
    - Embedded materials
    - Bones
    - UV coordinates
 - Supports merging into CFG/SCO files for roundtrip model editing
