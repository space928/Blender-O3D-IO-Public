# Blender-O3D-IO

Un plugin qui supporte les versions 2.79-3.x de blender afin d'import et exporter les fichiers `.sco`, `.cfg` et `.o3d` de OMSI.

![Blender-O3D-IO-Screenshot](https://user-images.githubusercontent.com/15130114/208222029-5f9c2eb7-1007-4c38-a06a-0f3214d0a2f6.png)

## Fonctionnalités
Blender-O3D-IO inclus un importeur de fichiers `o3d` rapide et un exporteur qui supporte toutes les fonctionnalités du 
format. Pour les modèles les plus complexes, les fichiers `.cfg` et `.sco` peuvent être importés et exportés. Les tuiles 
de map OMSI (fichiers `.map`) peuvent aussi être importés.

- Supporte entièrement le format O3D:
  - Normals de vertex explicite
  - Headers long (Version >= 3)
  - Encryption (nécessite le module privé `o3d_crypto.ps`)
  - Indices de triangle long
  - Graine d'encryption alternative
  - Matériaux embedded
  - Ossature
  - Coordonnes des UV
- Supporte plusieurs fonctionnalités des fichiers CFG/SCO:
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
  - Importe tous les fichiers references (fichiers o3d uniquement) et toutes les textures dans les fichiers CFG/SCO 
    comme des objets séparés.
  - Importe les fichiers en `.x` si un importateur compatible est installé (https://github.com/Poikilos/io_import_x)
- Importe les tuiles de map OMSI (fichiers `.map`): [WIP]
  - Importe tous les objets de la tuile
  - Importe le terrain et les matériaux de la tuile
  - Importe les splines et les convertis en mesh

## Installation
1. Va a la page release et télécharge la dernière release 
   (disponible [ici](https://github.com/space928/Blender-O3D-IO-Public/releases/latest)), cela devrait ressembler à 
   `Blender-O3D-IO-Public-0.2.3.zip` 
2. Ouvre Blender et vas dans `Edit->Preferences...` 
3. Va dans la section `Add-ons` et appuie sur le bouton `Installer...`
4. Sélectionne le fichier **zip** (ne le dézippez pas!) et appuie sur le bouton `Installer l'addon`
5. Tu devrais maintenant pouvoir importer les fichiers o3d/cfg/sco depuis `Fichier->Importer->OMSI Model Config (*.cfg, *.sco, *.o3d)`
6. Les tuiles de map peuvent être importé depuis `Fichier->Importer->OMSI Map Tile(*.map)`
7. Tu peux désormais exporter les fichiers o3d/cfg/sco depuis `Fichier->Exporter->Omsi Model Config (*.cfg, *.sco, *.o3d)`

## Conseils d'utilisation
OMSI et Blender ont des moyens distincts de gérer les fichiers 3D et les matériaux associés, donc il y a quelque 
endroits ou la conversion entre Blender et OMSI n'est pas parfaite, ceci est le plus visible lorsque quand on exporte 
l'exportateur doit faire des hypothèses afin d'exporter les fichiers correctement. L'exportateur a été fabriqué avec le 
but que l'on puisse exporter un fichier cfg qui soit identique que l'originel. Pour ce faire, le meilleur moyen 
d'apprendre comment il marche c'est d'essayer d'importer quelque fichiers et examiner comment l’importeur les configure 
dans Blender.

### Comment j'exporte un fichier CFG au lieu d'un fichier O3D?
L'exporteur decide quel type d'export utilise sur l'extension de fichier du fichier exporte. Afin d'exporter un fichier 
cfg avec tout les o3d nécessaire, il faut specifier l'extension de fichier `.cfg` lorsqu'on exporte. Lorsqu'on exporte 
q'un seul objet en tant que o3d, un seul fichier o3d est créé; d'un autre cote si on exporte de multiples objets blender 
en tant que o3d l'exporteur créé automatiquement des o3d différents pour chaque objet Blender, ceci est une 
fonctionnalité par défaut et ne peut pas être changé.

Par exemple si la scene contient les objets suivants:
```
Scene Collection
| > Body
| > Wheel_H
| > Wheel_VL
| > Wheel_VR
```
Si l'on active l'option "Export selection" dans le dialogue d'export, on peut contrôler quels objets sont exportés. 
Si on ne sélectionne que le `Body`, et qu'on l'exporte en tant que `Body.o3d` on retrouve bien q'un seul fichier o3d. 
Par contre, si l'on sélectionne tous les fichiers et on les exporte comme `Car.o3d` l'exporteur va créer automatiquement 
un fichier séparer pour chaque objet:
```
Car-Body.o3d
Car-Wheel_H.o3d
Car-Wheel_VL.o3d
Car-Wheel_VR.o3d
```
Si on l'exporte en tant que `Car.cfg` ce comportement reste le meme, juste que les fichiers o3d n'ont pas le prefix du 
nom et un fichier cfg est généré:
```
Car.cfg
Body.o3d
Wheel_H.o3d
Wheel_VL.o3d
Wheel_VR.o3d
```

### Les matériaux ne ressemblent pas comme il faut dans OMSI
Blender utilise un système de shading complètement different de celui de OMSI, donc il y a quelque limitations à prendre 
en compte lorsqu'on exporte des matériaux:
   - Certaines fonctionnalités requièrent un fichier cfg pour être exporter/fonctionner correctement (transparence, 
     envmaps, nightmaps, etc.)
   - Si les textures ne s'affichent pas dans OMSI vérifiez que:
     - Blender supporte des formats d'image que OMSI ne supporte pas, si possible utilise le format dds pour les 
       textures, ces derniers sont les plus optimises pour OMSI et vont en general charger plus vite. 
       (OMSI ne supporte que la compression DXT pour les fichiers DDS)
     - Faites attention que le fichier texture existe dans le bon dossier dans OMSI, l'exportateur converti tous les 
       chemins d'accès des textures en chemin relatif donc la texture doit être au bon endroit par rapport au fichier 
       o3d/cfg pour que OMSI puisse le trouver.
   - Seulement les champs des matériaux suivants sont exportés:
     - Couleur de base/couleur diffuse
     - Alpha
     - Couleur Spéculaire/Intensité Spéculaire
     - Rugosité/Rugosité Spéculaire (Lorsque la Rugosité est définie à une valeur inférieure à 0.1, l'envmap est active 
       automatiquement)
     - Couleur d'émission
     - 
     - Couleur de base de texture
     - Couleur d'Alpha
     - Texture Spéculaire
     - Normalmap (Traite comme une bumpmap)
     - Texture d'émission (exporte comme un `[matl_lightmap]` si la puissance d'emission est supérieur à 1, sinon c'est 
       exporte comme un `[matl_nightmap]`)
   - Les propriétés animées des matériaux ne sont pas supportés
   - Lorsqu'on utilise des nodes de shader (par défaut dans Blender >= 2.80), la **seule** node supporté comme input 
     sur un *BSDF Guidée* est le node de texture image.

### Comment l'importeur gère-t-il des donnes spécifiques a OMSI
L'importeur est fait de manière a preserver le maximum de donnes des cfg que possible, incluant des métadonnées qui ne 
sont pas utilisé par Blender comme par exemple les `[CTC_Texture]`, ces configurations sont stockées dans la case 
"Propriétés personnalisées" des objets en question. Les configurations spécifiques à la scene sont stockées dans la case 
"Propriétés personnalisées" du panel de la scene. Ces donnes peuvent être ajoutées ou modifiées et vont être exportés au 
bon endroit par l'exportateur, cependant il est tres facile de le casser. C'est pour cela que je ne recommande pas de 
modifier ces donnés tant que l'on ne sait pas ce que l'on fait.

### Lumiere parasite
Blender ne supporte pas les lumières parasite, mais rends possible leur placement `[light_enh_2]` l'importeur créé des 
objects EMPTY dans la position correct avec toutes les propriétés qui sont disponibles à modifier dans la section
"Propriétés personnalisées" dans l'onglet "Propriétés de l'objet" pour cet objet (a l'exception de la couleur, texture, 
et taille qui sont controller depuis les donnes de l'objet (la couleur est contrôlée depuis 
"Propriétés de l'objet->Affichage vue 3D->Couleur")).

### Lumières
Toutes les lumières point sont exportés comme des objets `[interiorlight]`. Seuls les propriétés suivantes peuvent être 
exportés:
- Position
- Puissance [Blender >= 2.80]
- Distance [Blender <= 2.79]
- Couleur
- Variable (depuis "Propriétés personnalisées")

Tous les projecteurs sont exportés comme des objets`[spotlight]`. Seuls les propriétés suivantes peuvent être exportés:
- Localisation
- Rotation
- Puissance [Blender >= 2.80]
- Distance [Blender <= 2.79]
- Couleur
- Taille
- Mélange

### Comment j’empêche des objets d'etre exportés?
Il y a deux méthodes: 

#### 1: 

Active la fonction "Export selection" dans le dialogue d'export (sur le côté droit) et sélectionne tous les objets que 
tu veux exporter.

#### 2:

Pour chaque objet tu peux l’empêcher d'etre exporter, si tu vas dans l'onglet "Propriétés", "Propriétés personnalisées" 
et ajoute une propriété du nom de "skip_export" (le type ne change rien étant donne que la valeur est ignorée).

### Animations
Actuellement elles ne sont pas importées, si un fichier importe contient des animations, elles devraient se faire 
re-exporters correctement. Mais aucune méthode n'existe actuellement pour convertir les animations Blender en animations 
OMSI. Ceci étant dit, les points de pivot des objets sont exportés correctement, et définir ceux si est vital lorsqu'on 
travaille avec des animations dans OMSI.

### LODs
Les LODs sont automatiquement exportés en fonction du nom de la collection (ou groupes dans blender 2.79). Les objets 
dans une collection du nom de la forme `LOD_X`, où `X` représente le nombre minimal de taille à l’écran sont exportés 
avec cet LOD.
