# Blender-O3D-IO

# Français:

Un plugin qui supporte les version 2.79-3.x de blender afin d'import et exporter les fichiers `.sco`, `.cfg` et `.o3d` de OMSI.

![Blender-O3D-IO-Screenshot](https://user-images.githubusercontent.com/15130114/208222029-5f9c2eb7-1007-4c38-a06a-0f3214d0a2f6.png)

## Fonctionnalités
Blender-O3D-IO inclus un importeur de fichiers `o3d` rapide et un exporteur qui supporte toutes les fonctionnalites du format. Pour les modeles les plus complexes, 
les fichiers `.cfg` et `.sco` peuvent etre importes et exportes. Les tuile de map OMSI (fichiers `.map`) peuvenet aussi etre importés.

- Supporte entièrement le format O3D:
  - Normals de vertex explicite
  - Headers long (Version >= 3)
  - Encryption (nécessite le module privée `o3d_crypto.ps`)
  - Indices de triangle long
  - Graine d'encryption alternative
  - Matériaux embedded
  - Ossature
  - Coordonnes des UV
- Supporte plusieurs fonctionalites des ficher CFG/SCO:
  - LODs
  - Imports et exports des matériaux avances tels que:
      - `[matl]`
      - `[matl_alpha]`
      - `[matl_transmap]`
      - `[matl_envmap]` & `[matl_envmap_mask]`
      - `[matl_bumpmap]` (Blender >= 2.80 only!)
      - `[matl_nightmap]` & `[matl_lightmap]`
      - ...
   - Éclairage intérieur et projecteurs
   - Lumiere parasite (`[light_enh]` et `[light_enh_2]`)
   - Importe tout les fichiers references (fichiers o3d uniquement) et toutes les textures dans les fichiers CFG/SCO comme des objets separes.
   - Importe les fichiers en `.x` si un importateur compatible est installe (https://github.com/Poikilos/io_import_x)
 - Importe les tuiles de map OMSI (fichiers `.map`): [WIP]
   - Importe tout les objets de la tuile
   - Importe le terrain et les matériaux de la tuile
   - Importe les splines et les convertis en mesh

## Installation
1. Va a la page release et télécharge la dernière release (disponible [ici](https://github.com/space928/Blender-O3D-IO-Public/releases/latest)), cela devrait ressembler a `Blender-O3D-IO-Public-0.2.3.zip` 
2. Ouvre Blender et vas dans `Edit->Preferences...` 
3. Va dans la section `Add-ons` et appuie sur le bouton `Installer...`
4. Sélectionne le ficher `**zip** (ne le dézippez pas!) et appuie sur le bouton `Installer l'addon`
5. Tu devrais maintenant pouvoir importer les fichiers o3d/cfg/sco depuis `Fichier->Importer->OMSI Model Config (*.cfg, *.sco, *.o3d)`
6. Les tuiles de map peuvent être importes depuis `Fichier->Importer->OMSI Map Tile(*.map)`
7. Tu peux désormais exporter les fichiers o3d/cfg/sco depuis `Fichier->Exporter->Omsi Model Config (*.cfg, *.sco, *.o3d)`

## Conseils d'utilisation
OMSI et Blender ont deux moyens distinct de gérer les fichiers 3D et les matériaux associes, donc il y'a quelque endroits ou la conversion entre Blender et OMSI
n'est pas parfaite, ceci est le plus visible lorsque quand on exporte l'exportateur doit faire des a hypothèse afin d'exporter les fichiers correctement. L'exportateur
a ete fabrique de telle sorte a ce que l'on puisse exporter un fichier cfg qui soit identique que l'originel. Pour se faire, le meilleur moyen d'apprendre comment il marche
c'est d'essayer d'importer quelque fichiers, et examiner comment l’importer les configure dans Blender.

### Comment j'exporte un fichier CFG au lieu d'un fichier O3D?
L'exporteur decide quel type d'export utilise sur l'extension de fichier du fichier exporte. Afin d'exporter un fichier cfg avec tout les o3d nécessaire, il faut specifier
l'extension de fichier `.cfg` lorsque on exporte. Lorsque on exporte q'un seul objet en tant que o3d, un seul fichier o3d est cree; d'un autre cote si on exporte de multiples
objets blender en tant que o3d l'exporteur cree automatiquement des o3d différents pour chaque objet Blender, ceci est une fonctionnalité par défaut et ne peut pas être changé.

Par exemple si la scene contient les objets suivants:
```
Scene Collection
| > Body
| > Wheel_H
| > Wheel_VL
| > Wheel_VR
```
Si l'on active l'option "Export selection" dans le dialogue d'export, on peut contrôler quels objets sont exportes. Si on ne sélectionne que le `Body`, et que on l'exporte en tant que
`Body.o3d` on retrouve bien q'un seul fichier o3d. Par contre si l'on sélectionne tout les fichiers et on les exporte comme `Car.o3d` l'exporteur va créer automatiquement un fichier séparer
pour chaque objet:
```
Car-Body.o3d
Car-Wheel_H.o3d
Car-Wheel_VL.o3d
Car-Wheel_VR.o3d
```
Si on l'export en tant que `Car.cfg` ce comportement reste le meme, juste que les fichier o3d n'ont pas le prefix du nom et un fichier cfg est génère:
```
Car.cfg
Body.o3d
Wheel_H.o3d
Wheel_VL.o3d
Wheel_VR.o3d
```

### Les matériaux ne ressemblent pas comme il faut dans OMSI
Blender utilise un système de shading complètement different de celui de OMSI, donc il y'a quelque limitations a prendre en compte lorsque on exporte des matériaux:
   - Certaines fonctionnalités requièrent un fichier cfg pour être exporter/fonctionner correctement (transparence, envmaps, nightmaps, etc...)
   - Si les textures ne s'affichent pas dans OMSI vérifiez que:
     - Blender supporte des formats d'image que OMSI ne supporte pas, si possible utilise le format dds pour les textures, ces derniers sont les plus optimises pour OMSI et vont en general charger plus vite. (OMSI ne supporte que la compression DXT pour les fichiers DDS)
     - Faites attention que le fichier texture existe dans le bon dossier dans OMSI, l'exportateur convertis tout les chemins d'acces des texture en chemin relatif donc la texture doit etre au bon endroit par rapport au fichier o3d/cfg pour que OMSI puisse le trouver.
   - Seulement les champs des matériaux suivants sont exportes:
     - Couleur de base/couleur diffuse
     - Alpha
     - Couleur Spéculaire/Intensité Spéculaire
     - Rugosité/Rugosité Spéculaire (Lorsque la Rugosité est définie à une valeur inférieur à 0.1, l'envmap est active automatiquement)
     - Couleur d'emission
     - 
     - Couleur de base de texture
     - Couleur d'Alpha
     - Texture Spéculaire
     - Normalmap (Traite comme une bumpmap)
     - Texture d'emission (exporte comme un `[matl_lightmap]` si la puissance d'emission est supérieur à 1, sinon c'est exporte comme un `[matl_nightmap]`)
  - Les propriétés animes des matériaux ne sont pas supportes
  - Lorsque on utilise des nodes de shader (par défaut dans Blender >= 2.80), la **seule** node supporté comme input sur un *Principled BSDF* est le node de texture image.

### Comment l'importeur gère t'il des donnes spécifiques a OMSI
L'importeur est fait de manière a preserver le maximum de donnes des cfg que possible, incluant des métadonnées qui ne sont pas utilise par Blender comme par exemple les `[CTC_Texture]`, ces configurations
sont stockes dans la case "Propriétés custom" des objets en question. Les configurations spécifiques a la scene sont stockees dans la case "Propriétés custom" du panel de la scene. Ces donnes peuvent etre ajoutes
ou modifies et vont être exportes au bon endroit par l'exportateur, cependant il est tres facile de le casser. C'est pour cela que je ne recommande pas de modifier ces donnes tant que l'on ne sait pas ce que l'on fait.

### Lumiere parasite
Blender ne supporte pas les lumières parasite, mais rends possible leur placement `[light_enh_2]` l'importeur cree des objects EMPTY dans la position correct avec toutes les propriétés qui sont disponibles a modifier dans la section
"propriétés custom" dans l'onglet "Propriétés de l'objet" pour cet objet (a l'exception de la couleur, texture, et taille qui sont controller depuis les donnes de l'objet (la couleur est contrôlée depuis "Propriétés de l'objet->Affichage->Couleur")).

### Lumières
Toutes les lumières point sont exportes comme des objet `[interiorlight]`. Seuls les propriétés suivantes peuvent être exportes:
- Localisation
- Energie [Blender >= 2.80]
- Distance [Blender <= 2.79]
- Couleur
- Variable (depuis "Propriétés custom")

Tout les projecteur sont exportes comme des objets`[spotlight]`. Seuls les propriétés suivantes peuvent être exportes:
- Localisation
- Rotation
- Energie [Blender >= 2.80]
- Distance [Blender <= 2.79]
- Couleur
- Taille
- Blend

### Comment j’empêche des objets d'etre exportes?
Il y'a deux méthodes: 

1: 

Active la fonction "Export selection" dans le dialogue d'export (sur le cote droit) et sélectionne tout les objets que tu veux exporter.

2:

Pour chaque objet tu peux l’empêcher d'etre exporter, si tu vas dans l'onglet "Propriétés", "Propriétés custom" et ajoute un propriété du nom de "skip_export" (le type ne change rien étant donne que la valeur est ignorée).

### Animations
Actuellement elles ne sont pas importes, si un fichier importe contient des animations elles devrait se faire re-exportées correctement. Mais aucune méthode n'existe actuellement pour Convertir les animations Blender en
animations OMSI. Ceci étant dit, les points de pivot des objets sont exportes correctement, et définir ceux si est vital lorsque on travaille avec des animations dans OMSI.

### LODs
Les LODs sont automatiquement exportes en fonction du nom de la collection (ou groupes dans blender 2.79). Les objets dans une collection du nom de la forme `LOD_X`, ou `X` représente le nombre minimal de taille a l’écran
sont exportes avec cet LOD.


# English:

A plugin supporting blender 2.79-3.x for importing and exporting OMSI .sco, .cfg, and .o3d files.

![Blender-O3D-IO-Screenshot](https://user-images.githubusercontent.com/15130114/208222029-5f9c2eb7-1007-4c38-a06a-0f3214d0a2f6.png)

## Features
Blender-O3D-IO includes a fast o3d file importer and exporter with full support for the format. For complex models, 
`.cfg` and `.sco` files can also be imported and exported. OMSI map tiles (`.map` files) can also be imported.

 - Fully supports O3D file format:
    - Explicit vertex normals
    - Long headers (version >= 3)
    - Encryption (requires private `o3d_crypto.py` module)
    - Long triangle indices
    - Alternative encryption seed
    - Embedded materials
    - Bones
    - UV coordinates
 - Supports many features in CFG/SCO files:
    - LODs
    - Imports and exports advanced material features including:
       - `[matl]`
       - `[matl_alpha]`
       - `[matl_transmap]`
       - `[matl_envmap]` & `[matl_envmap_mask]`
       - `[matl_bumpmap]` (Blender >= 2.80 only!)
       - `[matl_nightmap]` & `[matl_lightmap]`
       - ...
    - Interior lights and spotlights
    - Lens flares (`[light_enh]` and `[light_enh_2]`)
    - Imports all referenced models (o3d files only) and textures in the CFG/SCO as separate objects
    - Imports `.x` if a compatible importer is installed (https://github.com/Poikilos/io_import_x)
 - Imports OMSI map tiles (`.map` files): [WIP]
    - Imports referenced scenery objects
    - Imports terrain tiles and materials
    - Imports splines and converts them to meshes

## Installation
1. Go to the releases page and download the latest release (available 
[here](https://github.com/space928/Blender-O3D-IO-Public/releases/latest)), it should look like 
`Blender-O3D-IO-Public-0.2.3.zip`
2. Open Blender go to `Edit->Preferences...`
3. Go to the `Add-ons` tab and then press `Install...`
4. Select the **zip** file (do NOT unzip it) and press `Install Add-on`
5. You should now be able to import o3d/cfg/sco files from `File->Import->OMSI Model Config (*.cfg, *.sco, *.o3d)`
6. Map tiles can be imported from `File->Import->OMSI Map Tile (*.map)`
7. You can export o3d/cfg/sco files from `File->Export->OMSI Model Config (*.cfg, *.sco, *.o3d)`

## Exporter Tips
OMSI and Blender handle 3D models and materials fairly differently so there are a few areas where the conversion between 
Blender and OMSI is a bit imprecise, this is most notable when exporting as there are a few assumptions the exporter 
needs to make to export files correctly. The exporter is designed to try as closely as possible to export an imported 
cfg file identically to the original. As such, the best way to learn the specifics of the exporter is to try importing 
some files, and examine how the importer sets them up in Blender.

### How do I export CFG files instead of just O3D files?
The exporter decides what to export based on the file extension of the exported file. To export a cfg along with all 
its required o3d files, specify the `.cfg` file extension when exporting. When exporting a single mesh as an o3d, a 
single o3d file is produced; if on the other hand you're exporting multiple Blender objects as an o3d then the exporter
automatically creates separate o3d files for each Blender object, this behaviour can't be changed.

For instance if the scene contains the following objects:
```
Scene Collection
| > Body
| > Wheel_H
| > Wheel_VL
| > Wheel_VR
```
If we enable the "Export selection" option in the export dialog, then we can control which objects are exported.
With only the `Body` selected, if we export as `Body.o3d` we indeed end up with a single o3d file `Body.o3d`. If on the 
other hand we select all the objects and export as `Car.o3d` the exporter will automatically export separate files for 
each object:
```
Car-Body.o3d
Car-Wheel_H.o3d
Car-Wheel_VL.o3d
Car-Wheel_VR.o3d
```
If we export as `Car.cfg` then the behaviour is the same, except the o3d files are not prefixed with the file name and 
a cfg file is also generated:
```
Car.cfg
Body.o3d
Wheel_H.o3d
Wheel_VL.o3d
Wheel_VR.o3d
```

### Materials Don't Look Correct in OMSI
Blender uses a completely different shading system to OMSI so there are some limitations to consider when exporting 
materials:
 - Some material features require a cfg file to exported to work correctly (transparency, envmaps, lightmaps, etc...)
 - If textures aren't displaying in OMSI check the following:
   - Blender supports image formats that OMSI doesn't, if possible use dds files for textures, these are best optimised 
     for OMSI and will generally load faster. (OMSI only supports DXT compression in DDS files)
   - Make sure the texture file exists in the correct textures directory in OMSI, the exporter converts all texture 
     filepaths to relative paths, so the texture must be in the correct place relative to the o3d/cfg file for omsi to 
     find it.
 - Only the following material fields are exported:
   - Base Color/Diffuse Color
   - Alpha
   - Specular Color/Specular Intensity
   - Roughness/Specular Hardness (when the roughness is set below 0.1, the envmap is automatically enabled)
   - Emission Color
   - 
   - Base Color Texture
   - Alpha Texture
   - Specular Texture
   - Normalmap (treated as a bumpmap)
   - Emission Texture (exported as a `[matl_lightmap]` if the emission strength is greater than 1, otherwise it's 
     exported as a `[matl_nightmap]`)
 - Animating material properties is not supported
 - When using shader nodes (the default in Blender >= 2.80), the **only** node supported as an input to the *Principled 
   BSDF Node*, is the *Image Texture* node

### How Does the Importer Handle OMSI Specific Data?
The importer is designed to preserve as much data from the cfg file as possible, including metadata not used in Blender 
such as `[CTC_Texture]`, these configuration items are stored in the "Custom Properties" section of the relevant object 
in Blender. Scene specific config items are stored in the "Custom Properties" section of the Scene tab, the "Object 
Properties", "Data Properties" (Mesh/Light tab), and "Material Properties" tabs also have configuration items stored in 
their "Custom Properties" sections. This data can be added to or modified and will be exported in the correct place by 
the exporter, but it's very easy to break it. I don't recommend modifying this data unless you know what you're doing.

### Light Flares
Blender doesn't support light flares, but to allow for easy positioning of flares `[light_enh_2]` the importer creates
EMPTY objects in the correct position with the all of the properties of the flare available to modifiy in the "Custom 
Properties" section of the "Object Properties" tab for that object (with the exception of colour, texture, and size 
which are controlled from the object data properties (color is controlled from 
"Object Properties->Viewport Display->Color")).

### Lights
All point lights are exported as `[interiorlight]` objects. Only the following properties are exported:
 - Location
 - Light Energy (scaled down by a factor of 10 to be used as range) [Blender >= 2.80]
 - Light Distance [Blender <= 2.79]
 - Light Color
 - Light Variable (from "Custom Properties")

All spotlights are exported as `[spotlight]` objects. Only the following properties are exported:
 - Location
 - Rotation (converted to spot direction vector)
 - Light Energy (scaled down by a factor of 10 to be used as range) [Blender >= 2.80]
 - Light Distance [Blender <= 2.79]
 - Light Color
 - Light Spot Size
 - Light Spot Blend (Converted to inner angle)

### How Do I Prevent Objects From Being Exported?
There are two methods:
#### 1:
Enable the "Export selection" option in the export dialog (on the right-hand side of the file picker) and then select 
all the objects you want to export.

#### 2:
For each object you want to prevent from being exported, go to it's "Object Properties" tab, and in the 
"Custom Properties" section add a property with the name "skip_export" (the property type is unimportant as its value 
is ignored).

### Animations
Currently, these are not imported, if an imported cfg file contains animations they should be re-exported correctly 
(they are preserved in "Custom Properties"). But no method currently exists to convert Blender animation to OMSI 
animations. That being said, object pivot points are correctly exported, and setting these up correctly is vital to 
animations working correctly in OMSI.

### LODs
LODs are automatically exported based on collection (or groups in Blender 2.79) names. Objects in a collection with a 
name of the form `LOD_X`, where `X` is a decimal number representing the minimum screen size, are exported in that LOD.
