# Worship [C++ experiment]

![Worship Title Screen](/img/articles/worship/worship-blog.png "Worship Title Screen")

**Worship** is a small first-person shooter game I've been developing in my spare time for fun. While it was originally intended as a sequel to my [parody raycaster](/inferno/index.html), I have decided to decouple the games, while keeping most of the finished game assets. I deliberately constrained the game to render at 320x240 to see how much I can squeeze at such limitations.

Game features:

- simple FPS gameplay
- 3 weapons
- 3 enemy types
- 1 level for you to wander around and shoot anything that moves
- Doom-style menu system
- static and dynamic lighting
- occlusion culling based on raycasting

Since the game is an experiment, there's basically no story or ending condition at all.

![Gameplay](/img/articles/worship/screenshots.jpg)

You can also see the [gameplay video here](https://www.youtube.com/watch?v=8GHCplBW9tU).

The game is powered by **Mau** framework, a simple set of libraries and tools I'm making so I can reuse parts of my projects. Completed set of features includes:

- written in modern C++
- cross-platform
- easy to understand codebase
- state management
- OpenGL 3.3 renderer
- chainable screen-space effects
- 3D sound
- simple asset pipeline with utility scripts
- CMake support

While the framework is still heavily in development, pet projects like these help me notice flaws and make incremental changes and redesigns.

## Build Instructions

You can grab the source at: [https://github.com/staniks/worship-mirror](https://github.com/staniks/worship-mirror).

Clone the repository. You'll need **SDL2** and **SDL2_mixer** packages. Within the root of the project, run:

    mkdir build
    cd ./build
    cmake ..

Before running the game, you'll need the data archive. You can either compile it yourself or download it from the releases section along with the binaries. **If you want to compile the assets yourself, you will need Pillow (Python imaging library) which is used by the texture converter.**

    python3 compile-assets.py  [--skip-textures]

## Asset Workflow

As you've probably noticed, most of the assets are actually pre-rendered sprites. This is a technique used since ye olde times and seems to have made a sort of comeback with recent titles like _Ion Fury_.

![Sprite workflow](/img/articles/worship/sprite-workflow.png "Sprite workflow")

The workflow I used for this project is simple:

1. Model and animate the object in Blender
2. Set-up rendering scripts (Blender's Python API)
3. Render the animations into series of PNG files with specific naming conventions
4. Convert the images into my framework's internal texture format

### Archive

Remember the DOS era, where games usually had their assets packed in some sort of binary blobs? For example, Doom's WAD files or Quake PAK archives. I wanted to do something similar for this project, so I made a small archive format. The structure is really simple:

- magic/signature
- resource descriptors
- resource data

Resource descriptors contain:

- type (texture, shader, sound...)
- name
- offset
- size
- checksum

Resource type helps the framework determine how to instantiate the asset during preloading sequence. Most resources are preloaded during game startup since they're small and relatively cheap to hold in memory. If you look at the source code, there are several Python scripts which are used to prepare assets and compile them into the archive. They're not particularly robust or fast, but it was good enough for this use-case.

Checksum is there just to tell the engine not to even bother instantiating the resource if the file was somehow corrupted or casually tampered with.

There's no compression or obfuscation of any kind, so if you open up the archive with a hex editor, you could even figure out the format structure without even looking at the structs.

### Emission Maps

If you look into the data/ directory, you'll notice most textures have been split in two flavors:

- diffuse textures
- emission textures

Diffuse textures contain color information, like so:

![Diffuse Example](/img/articles/worship/rocket-launcher-diffuse-0001.png "Diffuse Example")

Emission textures contain brightness information.

![Emission Example](/img/articles/worship/rocket-launcher-emission-0001.png "Emission Example")

This allows us to display parts of texture with brightness regardless of current lighting, and thus give impression that something is glowing in the dark, especially when coupled with the bloom shader.

![Diffuse and Emission Example](/img/articles/worship/screenshot.png "Diffuse and Emission Example")

### Directional sprites

Enemies change their sprite based on their direction and the location of the player in an attempt to give the impression of a 3D object. As you might expect, this is somewhat expensive in terms of memory usage, but works rather nicely.

![Enemy directional sprite](/img/articles/worship/enemies.png)

### Level Editing

For level editing I used [Tiled](https://www.mapeditor.org/). It's free, cross-platform and general-purpose. It exports a JSON file which is easy to parse and even supports plugin creation for custom exporters.

## Poor man's occlusion culling

Tile-based level layout makes a lot of things simple, including occlusion culling. So I did someting similar to what Wolfenstein 3D did - performed a raycast for every screen column and checked which chunks the ray has traversed.

By chunks, I mean regions of tiles. The level consists of tiles, but the engine divides the level into "chunks" because of batching. Batching is done per chunk to minimize draw calls. Basically, instead of telling GPU to draw tiles one by one, we tell it to draw a bunch of them at once, and this is much faster.

## Lighting algorithm

I wrote about the simple static lighting algorithm I use in [a blog](/blog-lightmaps.html).

Apart from the static lighting, object are lit by dynamic lights as well. Pickups, projectiles, explosions and particles emit faint glow which helps them stand out from the scenery. It's a forward lighting approach - each chunk or object can be lit by up to N nearest point lights. There is some overhead in calculating which of the lights should be taken into account, but it doesn't impact performance much.

## What could have been done better?

Where do I even start?

I've littered the code with **TODO** comments in case someone is looking for a challenge. Issues range from simple ones like this...

    namespace mau
    {
        // Returns adler32 checksum of given data.
        // TODO: refactor to use mau::span
        uint32_t adler32(byte_t* data, size_t size);
    }

...to more complex ones, like refactoring the spatial partitioning and collision detection systems.

I'm not particularly satisfied with the way I wrote the renderer, it feels a somewhat inefficient, especially the batching part. I'll definitely be looking into literature again for this one. I'm not happy with the way I wrote shaders either, and that's something I also plan on tackling soon.

## License?

Do whatever you want as long as you respect the GNU GPLv3. Create a story campaign. Create more levels. Make the grenade launcher fire rubber ducks instead of grenades. Create a battle royale spinoff.

Also, while most of the other assets were created by me, the sounds were not - they have separate licenses themselves. Look into data/sounds for more info.

It's not mandatory, but if you ever make something off of this, I'd seriously like to hear from you. Tweet me [@Sklopec](https://twitter.com/Sklopec).