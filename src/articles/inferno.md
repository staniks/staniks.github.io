<p><img src="/img/articles/inferno/banner.png" alt="Banner" title=""></p>

<h1>Inferno - learning project [C++, SDL2]</h1>

<p>Inferno is a small raycaster FPS I wrote as an exercise in C++ and graphics. </p>

<p>Features:</p>

<ul>
<li>3 distinct weapons</li>
<li>3 enemy types</li>
<li>JRPG-style dialogue system</li>
<li>custom pre-rendered and hand-drawn graphics</li>
<li>no sound whatsoever</li>
<li>far-fetched references to my alma mater</li>
<li>laughably terrible plot</li>
</ul>

<p><img src="/img/articles/inferno/gameplay1.gif" alt="Gameplay" title="">
<img src="/img/articles/inferno/gameplay2.gif" alt="Gameplay" title="">
<img src="/img/articles/inferno/gameplay3.gif" alt="Gameplay" title="">
<img src="/img/articles/inferno/gameplay4.gif" alt="Gameplay" title=""></p>

<h2>Source</h2>

<p>You can get the source code <a href="https://github.com/staniks/inferno-mirror">here</a>.</p>

<p>While the source is released under GPL, keep in mind the assets are <strong>NOT</strong> - they're not to be used anywhere else. Besides, I pity the poor soul who is desperate enough to steal and use such awful artwork in their asset-flipper game. </p>

<h2>Note</h2>

<p>I'd like to point out that I'm no expert in the field. This was a learning project, and you should treat it as such if you intend to learn from it - it's a freaking gallery of bad practice and should be taken with a <strike>grain</strike> fistful of salt.</p>

<h2>Constraints</h2>

<p>The goal was to develop a game similar to Wolfenstein 3D, but also give it a soul of its own. Before diving into development, I had setup some constraints to make it more interesting:</p>

<ul>
<li>No using OpenGL, DirectX, or similar graphics API</li>
<li>No using GLM or similar algebra library</li>
<li>Environment rasterization must be done via raycasting</li>
<li>Target resolution is 320x200</li>
</ul>

<h2>"Art"</h2>

<p>I'll be honest here - I'm no artist. I can't draw. However, I wanted all of the art to be custom, and since it's a non-profit portfolio project, hiring an artist would be an overkill. Luckily, I had some experience with Blender and photo editing programs, which turned out somewhat useful.</p>

<p>All of the weapons were created in Blender, and then rendered from first-person perspective to be rendered in-game as textures.</p>

<p><img src="/img/articles/inferno/art1.jpg" alt="Art" title=""></p>

<p>Enemies were also created in Blender, but they were also rigged and animated. As you can clearly see, I didn't really outdo myself here.</p>

<p><img src="/img/articles/inferno/enemy.png" alt="Art" title=""></p>

<p>Since I used only forward kinematics, the result is godawful, but at least I learned a valuable lesson here - invest into learning IK in the future. Or even better, just hire an artist, they would be able to do a much better job in a shorter time.</p>

<p><img src="/img/articles/inferno/enemy.gif" alt="Art" title="">
<img src="/img/articles/inferno/enemy2.gif" alt="Art" title="">
<img src="/img/articles/inferno/enemy3.gif" alt="Art" title=""></p>

<h2>Raycasting</h2>

<p><em>What is raycasting anyway?</em></p>

<p>Basically, it's a rasterization technique which takes some shortcuts to make things faster in comparison to true 3D renderers. </p>

<p>Let's assume we have an environment with a bunch of walls, and we want to render it in first-person view. For each column of the screen, we do something like this:</p>

<ol>
<li>Cast a ray at an angle based on the column's position on the screen, player's rotation and horizontal field of view</li>
<li>Find the intersection point of the ray and the wall</li>
<li>Project the intersection point to the camera plane</li>
<li>Calculate wall height in screen-space based on distance of intersection point to the camera plane</li>
<li>Render the vertical wall stripe by sampling the wall texture</li>
</ol>

<p>If you've ever used some form of a game engine, you probably know that raycasting is a somewhat expensive operation because it involves querying spatial partitioning system and performing tests on geometry within relevant cells.</p>

<p>However, using a square grid simplifies things and allows very fast raycasting. I won't go into details here because this paper already explains it very well: <a href="http://citeseerx.ist.psu.edu/viewdoc/download?doi=10.1.1.42.3443&amp;rep=rep1&amp;type=pdf">A Fast Voxel Traversal Algorithm</a>.</p>

<p><img src="/img/articles/inferno/raycast1.gif" alt="Rendered walls" title="">
<img src="/img/articles/inferno/raycast2.gif" alt="Rendered walls" title=""></p>

<p><em>That's great for walls, but what about monsters, pickups and particles?</em></p>

<p>Well, we don't use the raycasting for those. Instead, when we draw walls, we fill a 1-dimensional Z-buffer which allows us to test whether parts of entity are visible. Then we use the projected entity position to draw the sprite on screen, querying the Z-buffer for each column occupied by entity in screen space.</p>

<p><em>What about multiple entities? Surely, sometimes they would overlap?</em></p>

<p>That's where the <em>poor man's spatial partitioning system</em> comes in. Cells keep a set of entities that intersect them. Entities are in charge of telling cells when they touch them or leave. When we're raycasting for walls, we query each cell for monsters within, and keep a set of those (remember, set is a data structure where every entry is unique, so there are no duplicates). Then, when rendering entities, we sort them back to front, and then render them in that order - this makes entities closer to the camera to seemingly occlude the entities behind them.</p>

<p><img src="/img/articles/inferno/occlude1.gif" alt="Overlapping entities" title="">
<img src="/img/articles/inferno/occlude2.gif" alt="Overlapping entities" title=""></p>

<h2>Interesting Bits</h2>

<h3>Render Device</h3>

<p>Render device is an abstraction of a buffer in which the user can write raw RGBA pixel data. If you already skimmed the source, you've probably noticed that we're using SDL_Texture here, which is an abstraction for OpenGL or DirectX texture, depending on the platform.</p>

<p><em>Why, though? Why not plain SDL_Surface?</em></p>

<p>Well, both performance and convenience. Raycasting doesn't scale well with horizontal resolution. We're casting a ray for each screen column, which would point to O(N) complexity, but it's actually more than that - when we're rasterizing, we're traversing parts of each column in order to rasterize the wall stripe. In worst case, the player is so close to the wall that we're rendering wall stripes on the whole screen - O(N²) complexity.</p>

<p>This becomes even worse when you take cache efficiency into consideration. For bigger screen resolutions, you can expect more cache misses when rendering, depending on your CPU's cache size, and rendering becomes even slower. This could, of course, be mitigated by transposing the screen texture so that we're rendering vertical stripes more efficiently, but I found the performance gain for the target resolution (320x200) to be negligible on modern CPUs.</p>

<p>You have probably noticed that raycasting could be easily parallelized. It could, and I tried that. I split the screen into even chunks and use the main thread as a load balancer for the worker threads which render each stripe to the backbuffer before flipping it to foreground. Turns out the thread synchronization overhead was higher than rendering time at target resolution, thus actually slowing down the renderer, but the renderer did the job better with larger resolutions. However, when resolution was increased sufficiently (1080p), performance degraded up to the point where it was unacceptable. And it was ugly - raycasters just don't look good without pixelation (this is highly subjective, though).</p>

<p><em>So how do we render the game at modern resolutions with acceptable performance and without turning the player's CPU into a fire hazard?</em></p>

<p>We cheat, of course.</p>

<p>Instead of rendering the game at user's resolution, we obtain write access to the SDL_Texture's raw pixel data and render everything there, at target resolution (320x200). Then, we use the hardware acceleration to scale it up to an arbitrary resolution, without filtering (for the retro look) and with letterboxing if needed.</p>

<p>This way, we're always rendering the environment at base resolution, regardless of the real screen resolution. We get to keep the performance and the uniform retro look across different resolutions.</p>

<p>Not exactly rocket science, but it does the trick.</p>

<h3>Lookup Tables - Yay or nay?</h3>

<p>Back in the day, games used to precompute sine and cosine tables to avoid having to compute values at runtime. Nowadays, processors even have dedicated trigonometry instructions which allow for fast computation. However, actual generated code of STL trigonometry functions is system-dependent. On some systems the compiler might generate a dedicated x86 sine instruction, while on others it might use <a href="https://sourceware.org/git/?p=glibc.git;a=blob;f=sysdeps/ieee754/dbl-64/s_sin.c;hb=HEAD#l281">sin implementation from GNU libm</a>. MSVC simply produces instruction:</p>

<pre><code>call sin
</code></pre>

<p>which is a call to some closed-source assembly function which I have no idea how to get to in human-readable form.</p>

<p><em>(Thanks to Picard and Zoidberg of fer2.net for pointing me in the right direction here.)</em></p>

<p>Nevertheless, I decided to implement both to just for the fun of it. I ran both variations with an iteration count of 100,000,000 to see how much better calculating sine at runtime would turn out.</p>

<pre><code>// Naive lookup table implementation
inline float LookupTables::Sin(uint32 pAngleUnits)
{
    return mSin[pAngleUnits % LookupResolutionSin];
}

// Naive lookup table test
for (size_t i = 0; i &lt; iterationCount; ++i)
{
    // LookupTables::Sin is inline, so there's no stack frame overhead
    volatile float a = LookupTables::Sin(Random::Uint());
}

// STL test
for (size_t i = 0; i &lt; iterationCount; ++i)
{
    volatile float a = std::sinf(Random::Float());
}
</code></pre>

<p>On average, my naive lookup table implementation took 612ms, and std::sinf took 38ms. That's pretty cool.  </p>

<p>In essence, using precomputed tables for sine and cosine on modern CPUs might actually make things <em>slower</em>. I guess. <em>Please correct me if my conclusions were wrong here.</em></p>

<p>Again, cache is a factor here (lookup table size matters), but running the test with smaller lookup table sizes produced virtually identical results on a modern machine.</p>

<p>Besides, using a precomputed table would mean polluting the code with these arbitrary angle units instead of radians, which might make code somewhat hard to read. It would also mean having to perform conversions between radians and these units at some point.</p>

<h3>Lexical analyzer</h3>

<p>A small lexical analyzer was implemented to simplify scripting dialogue, reading font descriptions and similar text data without having to worry about spaces, newlines and quotes. Supports strings and escaping characters. It's rather ugly, and could be improved by using some kind of a generic state machine instead of a bunch of branching statements, but it works.</p>

<p>For example, it allows easy parsing of dialogue scripts.     </p>

<pre><code>BEGIN_DIALOGUE "gossip_toilet"
    BEGIN_ENTRY
        "dialogue_persephone.png"
        "PERSEPHONE"
        "Can't help but wonder... Who leaves toilet paper rolls scattered around?"
    END_ENTRY
    BEGIN_ENTRY
        "dialogue_computer.png"
        "FACULTY COMPUTER"
        "Query unclear."
    END_ENTRY
    BEGIN_ENTRY
        "dialogue_persephone.png"
        "PERSEPHONE"
        "It's just awfully convenient. That's all."
    END_ENTRY
END_DIALOGUE
</code></pre>

<p>The analyzer would extract the following tokens as strings:</p>

<pre><code>BEGIN_DIALOGUE
gossip_toilet
BEGIN_ENTRY
dialogue_persephone
PERSEPHONE
Can't help but wonder... Who leaves toilet paper rolls scattered around?
END_ENTRY
(...)
</code></pre>

<p>These tokens are then used in another component to construct actual in-game dialogue.</p>

<h3>Artificial Intelligence</h3>

<p>The AI is as dumb as it gets - it begins unaware, casting a ray in the player's direction continuously. If the ray hits a wall before it reaches the player, the monster remains unaware. Once player enters the monster's field of vision, it becomes aware and starts moving into range. Once in range, it fires at the player until he goes out of range or the monster dies.</p>

<p><img src="/img/articles/inferno/ai.gif" alt="Deep-learned AI on the blockchain" title="">
<img src="/img/articles/inferno/gameplay1.gif" alt="Gameplay" title=""></p>

<p>It would be cool to see some kind of avoidance behavior in action to prevent monsters from running into each other and getting stuck. Pathfinding would also be a trivial matter due to square grid - it would be simple to construct a navigation mesh.</p>

<h2>Final words</h2>

<p>While I'm somewhat satisfied with the way it turned out, the project is filled with issues, and while they could be fixed, I no longer plan on maintaining it - it's boring, tedious work, and a lot of things should be refactored entirely.</p>

<p>The purpose of the project was fulfilled - to get some knowledge and experience. I learned how to do some things, but more importantly, I learned how <em>not</em> to do some things.</p>

<p>I still have a long way to go, but I believe developing this game has made me a bit better developer in general.</p>

<p>Thanks for checking it out!</p>