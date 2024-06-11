![Banner](/img/articles/serious-engine/banner.jpg "Banner")

Croteam released the [Serious Engine 1 source code](https://github.com/Croteam-official/Serious-Engine) under GNU GPL v2 in 2016, and I've wanted to check it out for quite a while now. My observations here are based on reading and debugging this particular codebase and not reverse-engineering the classics released on GOG and Steam. Keep in mind that comments in code snippets have been replaced to provide more context. Also, some of my conclusions here may be wrong, so you can send me a message over at [@Sklopec](https://twitter.com/Sklopec) if you feel like something needs correction.

>**NOTE:** *This isn't an in-depth technical analysis, but an overview with more focus on the concepts rather than the implementation. I have skipped over a lot of things for the sake of simplicity. Also, the following sections assume you have at least a vague idea of how Serious Sam looks and plays.*

# Table of Contents

<div class="table-of-contents">
<ol>
    <li>
        <a href="#overview">Overview</a>
        <ol>
            <li><a href="#floating-point-determinism">Floating Point Determinism</a></li>
            <li><a href="#tick-vs-frame">Tick vs. Frame</a></li>
        </ol>
    </li>
    <li>
        <a href="#networked-multiplayer">Networked Multiplayer</a>
        <ol>
            <li>
                <a href="#the-packet-layer">The Packet Layer</a>
                <ol>
                    <li><a href="#the-lifecycle-of-a-connection">The Lifecycle of a Connection</a></li>
                    <li><a href="#master-buffers">Master Buffers</a></li>
                    <li><a href="#packet-routing">Packet Routing</a></li>
                    <li><a href="#establishing-a-connection">Establishing a Connection</a></li>
                    <li><a href="#reliability">Reliability</a></li>
                    <li><a href="#offline-play">Offline Play</a></li>
                </ol>
            </li>
            <li>
                <a href="#the-message-layer">The Message Layer</a>
                <ol>
                    <li><a href="#message-compression">Message Compression</a></li>
                    <li><a href="#message-security">Message Security</a></li>
                    <li><a href="#message-dispatcher">Message Dispatcher</a></li>
                </ol>
            </li>
             <li>
                <a href="#the-game-session-layer">The Game Session Layer</a>
                <ol>
                    <li><a href="#hosting-a-game">Hosting a Game</a></li>
                    <li><a href="#joining-a-game">Joining a Game</a></li>
                    <li><a href="#starting-a-demo-playback">Starting a Demo Playback</a></li>
                    <li><a href="#the-main-loop">The Main Loop</a></li>
                    <li><a href="#prediction">Prediction</a></li>
                </ol>
            </li>
        </ol>
    </li>
    <li>
        <a href="#conclusion-and-additional-thoughts">Conclusion and Additional Thoughts</a>
        <ol>
            <li><a href="#comparison-with-doom-and-quake">Comparison with Doom and Quake</a></li>
            <li><a href="#message-portability">Message Portability</a></li>
            <li><a href="#final-thoughts">Final Thoughts</a></li>
        </ol>
    </li>
</ol>
</div>

# Changelog

- **2020-11-05** - published.
- **2024-06-11** - fix typo.

# Overview <a name="overview"></a>

---

**Serious Sam** was built from the ground up as a multiplayer game. In a way, it's multiplayer even when you're playing the singleplayer campaign. While this idea may seem unusual at first, it's really just a clever way of abstraction. Let's explore how it works.

Serious Engine supports:

- singleplayer - offline campaign
- multiplayer - online, LAN or local co-op and various game modes
    - supports multiple players on the same client via split-screen!
- demo recording and playback

Let's look at the demo functionality first. Serious Engine allows recording and reproduction of gameplay clips or *demos*. Both multiplayer and singleplayer game sessions can be recorded. In order to record a game, the most naive solution would be to persist the game state of every tick into a file.

However, such an approach has a problem - demo files would be ridiculously large.

Instead, Serious Engine records the entire game state at the beginning of the recording, and then, each tick, records something called **game stream blocks**. For now, think of these as messages which describe events in the game. They can be of these types:

    MSG_SEQ_ALLACTIONS,      // Player actions. See below.
    MSG_SEQ_ADDPLAYER,       // Add a new player to the game.
    MSG_SEQ_REMPLAYER,       // Remove a player from the game.
    MSG_SEQ_PAUSE,           // Pause or unpause the game.
    MSG_SEQ_CHARACTERCHANGE, // Change an aspect of player's character.

It's not important that you understand these context of these message types right now - we'll get to that later. For now, let's focus on message type `MSG_SEQ_ALLACTIONS`, because this is key to understanding how the whole thing works. This particular message type is processed in `CSessionState::ProcessGameTick`:

    FOREACHINSTATICARRAY(ses_apltPlayers, CPlayerTarget, itplt) {
        if (itplt->IsActive()) {
            // Extract action from message passed as parameter.
            CPlayerAction paAction;
            nmMessage>>paAction;

            // Apply the action to the CPlayerTarget.
            itplt->ApplyActionPacket(paAction);
        }
    }

The engine deserializes several `CPlayerAction` objects from the message, one for each active player (since multiplayer games can be recorded as well), and applies these packets. Let's take a look at the `CPlayerAction` class to see what these packets actually are.

    class ENGINE_API CPlayerAction {
    public:
        FLOAT3D pa_vTranslation;
        ANGLE3D pa_aRotation;
        ANGLE3D pa_aViewRotation;
        ULONG   pa_ulButtons;
        __int64 pa_llCreated;

        // ...
    }

`CPlayerAction` describes the player's state:

- player character velocity in world-space (`pa_vTranslation`)
- player character rotation in world-space (`pa_aRotation`)
- player view rotation in world-space (`pa_aViewRotation`)
- buttons currently held down (`pa_ulButtons`, application defined, independent of control mapping scheme)
- timestamp in milliseconds (`pa_llCreated`, from [TSC](https://en.wikipedia.org/wiki/Time_Stamp_Counter))

These messages are generated by the Engine each tick during gameplay as the player interacts with the game (presses buttons, moves the mouse and/or thumbsticks). The messages are continuously serialized during recording and written into the demo file.

So how does reproduction work? The idea is simple - the Engine assumes everything in the game is completely predictable, and the players are the only ones with the power to change things. So in order to record the demo, the Engine only needs to record the entire game state once, and then only record the actions players perform each tick. In order to perform playback, the Engine deserializes the initial game state from the demo file, and then deserializes and applies player actions each tick as if the player was playing the game.

Neat, isn't it?

There's a caveat, though - **this means the Engine's game model has to be completely deterministic.** And it is. You can see an example of this if you peek into the `CEntity` implementation:

    ULONG CEntity::IRnd(void)
    {
        return ((_pNetwork->ga_sesSessionState.Rnd()>>(31-16))&0xFFFF);
    }

where `CSessionState::Rnd()` is a pseudo-random number generator whose seed is part of the game state and is therefore initialized during game state deserialization:

    void CSessionState::Read_t(CTStream *pstr)  // throw char *
    {
        // ...
        (*pstr)>>ses_ulRandomSeed;
        // ...

This makes sure the Engine is able to reproduce the exact same scenario every time we play the demo. If we would, say, use a truly random number generator for some game logic, or even a pseudo-random generator with differing seed, we would get different results every time - the famous **desynchronization**.

## Floating Point Determinism <a name="floating-point-determinism"></a>

There's also the matter of potential desynchronization due to floating point numbers. However, since Serious Sam on PC was originally released on Windows only, they could get away with using one compiler for everything, thus eliminating any sync issues that would emerge due to differences in C runtime library, like different implementations of trigonometry functions.

Similar issues can also arise due to differences in FPU precision. For example, the renderers are DLLs, and different clients might use different renderers. Renderers call various APIs (OpenGL, DirectX), and function calls in some of them might set FPU precision to different than expected. Serious Engine seems to have that covered as well. You can see precision guards like these, sprinkled around:

    CSetFPUPrecision FPUPrecision(FPT_24BIT);

Upon this object's construction, `_control87` function (MSVC specific) is used to cache the current FPU precision, then apply the new one. Once the object goes out of scope, the cached FPU precision is restored.

In theory, problems like these could also occur due to rounding control, but I haven't seen it explicitly set anywhere in the engine. There's this assert though, but this is just a query.

    ASSERT((_controlfp(0, 0)&_MCW_RC)==_RC_NEAR);

Maybe it just wasn't that big of a deal - perhaps the rounding differences would be small enough not to accumulate significantly over the relatively short time that a session lasts, and thus, not produce any noticeable desynchronization.

## Tick vs. Frame <a name="tick-vs-frame"></a>

Notice how I use the word **tick** instead of **frame**. This is because the game logic tickrate is decoupled from the rendering framerate. Rendering framerate varies depending on the hardware and settings, but seems to be capped at **500 frames per second** internally. However, the game logic rate is constant and limited to **20 ticks per second**. But why do we see smooth movement and animation?

**Interpolation**. Serious Engine interpolates between the current and the previous game tick based on time passed between. Try opening the in-game console (`~` key) and typing this to see how the game looks and feels without interpolation:

    /net_bLerping=0

It's kind of like playing a modern console exclusive. So how does Serious Engine smooth this out?

Animations and movement are interpolated with simple linear interpolation (lerp):

    interpolated_state = old_state + (new_state - old_state) * factor;

where `factor` is a floating point value in range `[0.0f, 1.0f]`. The factor in a particular moment in time is calculated as follows (pseudocode):

    // Time is in seconds.
    float real_delta = time_since_session_started;
    float tick_delta = time_of_last_tick - time_of_first_tick;

    // 20 FPS logic framerate.
    static constexpr float tick_quantum = 1 / 20.0f;

    float factor2 = 1.0f - (tick_delta - real_delta) / tick_quantum;

Or illustrated, if don't mind my terrible handwriting...

![Ticks explained](/img/articles/serious-engine/frametick.png "Ticks explained")

You can also see the implementation in `CSessionState::SetLerpFactor`. You will notice there are two interpolation (`Lerp`) factors - one is for predicted movement, and one is for non-predicted. For now, don't worry about predicted movement - we'll get to prediction and explain how it works later.

Now that we've covered the basic concept of the demo recording and reproduction, think about this: instead of recording the course of the game into a file to be reproduced later, we could send it over the network to be reproduced in real time as we play the game with another person. That is the basic idea of Serious Engine multiplayer.

# Networked Multiplayer <a name="networked-multiplayer"></a>

---

Unfortunately, the internet is a much more complicated environment than a file on your disk drive. Serious Sam is a fast paced game, and making things work fast over the internet is somewhat tricky, especially if you consider the fact that Serious Sam came out in the early 2000s, when a noticeable amount of people were still using 56k modems.

As you may have already guessed, Serious Sam employs a multiplayer model in which every player runs their own simulation and merely receives instructions on what the players have done, much like the demo system. If you glance at the code, you might see function names like `CNetworkLibrary::StartPeerToPeer_t`, but this is somewhat misleading - Serious Sam's networking isn't really peer to peer, even though the logic is processed akin to the old lockstep multiplayer games.

Serious Engine's networking model is actually client-server.

The basic idea is that, for a single multiplayer session, there is a single server, and the clients connect to it. The server receives messages from clients, processes them, and relays relevant information to all the clients. The clients then use this information to advance the state of their simulation.

This concept introduces the server as the "middleman" and avoids a myriad of issues which could emerge in a classic peer-to-peer model. For example, in case of desynchronization in pure peer-to-peer, it isn't trivial to determine whose game state is legitimate. Even worse, since public IPv4 addresses are in short supply, many people play behind NATs, and directly interfacing with such clients via UDP would often involve ugly hacks like NAT hole punching, or may not even work at all.

## The Packet Layer <a name="the-packet-layer"></a>

Serious Engine uses UDP - a connectionless, "fire and forget" protocol. UDP packets begin with a struct like this, followed by packet data.

    struct udp_packet_header_t
    {
        uint16_t src_port; // Source port.
        uint16_t dst_port; // Destination port.
        uint16_t length;   // Packet length (including the header).
        uint16_t checksum; // Checksum.
    };

UDP packets can arrive at their destination out of order, or may not arrive at all. This is a significant problem when playing over the internet, so Croteam implemented their own, custom protocol on top of UDP to achieve reliability and packet ordering. Let's take a look at the `CPacket` structure.

> **NOTE:** This isn't actually what's being transmitted, but rather an internal representation. `pa_pubPacketData` is the data that will eventually end up being sent over the network.

    class CPacket {
    public:
        ULONG       pa_ulSequence;
        UBYTE       pa_ubReliable;
        SLONG       pa_slSize;
        SLONG       pa_slTransferSize;
        UBYTE       pa_ubRetryNumber;
        CTimerValue pa_tvSendWhen;
        UBYTE       pa_pubPacketData[MAX_PACKET_SIZE];
        CListNode   pa_lnListNode;
        CAddress    pa_adrAddress;

        // ...
    };

Packet ordering and deduplication is achieved via **sequence number** (`CPacket::pa_ulSequence`). This is incremented every time the engine sends a packet. When packets are received or prepared for sending, they are inserted into a corresponding packet buffer (`CPacketBuffer`), at a position based on this sequence number (i.e. packet of highest index is appended to the end of the buffer). When a packet with an already encountered sequence number is received, it is discarded to prevent duplication.

Reliability is handled via `CPacket::pa_ubReliable` flag field. The basic idea is to have two types of packets.

- **Unreliable packets** - these are sent and discarded. They are used when the Engine doesn't care if the message has reached the destination or not.

- **Reliable packets** - when these are sent, Serious Engine expects to get an **acknowledge packet** (in further text: **ACK**) to confirm the destination has received the packet. In case the ACK isn't received after some time (timeout), the Engine sends the original packet again - this is called **retransmission**.

`CPacket::pa_ubReliable` is a flag field with the following flags:

    #define UDP_PACKET_UNRELIABLE       0
    #define UDP_PACKET_RELIABLE         1
    #define UDP_PACKET_RELIABLE_HEAD    2
    #define UDP_PACKET_RELIABLE_TAIL    4
    #define UDP_PACKET_ACKNOWLEDGE      8
    #define UDP_PACKET_CONNECT_REQUEST	16
    #define UDP_PACKET_CONNECT_RESPONSE	32

If a packet is to be considered reliable, Serious Engine sets the `UDP_PACKET_RELIABLE` flag. It is also worth noting that reliable packets can form streams to carry more data than fits into a single packet. The Engine adds `UDP_PACKET_RELIABLE_HEAD` flag to the first packet in the stream, and `UDP_PACKET_RELIABLE_TAIL` to the last packet. If the Engine is sending a single reliable packet (i.e. not part of a stream), both `UDP_PACKET_RELIABLE_HEAD` and `UDP_PACKET_RELIABLE_TAIL` flags are set for that packet.

Unreliable packets can't form streams because that wouldn't make any sense - packet loss could result in a corrupted stream.

**Acknowledge (ACK)** packets are sent for received reliable packets. ACK packets are unreliable by design, and only have `UDP_PACKET_ACKNOWLEDGE` flag set. A single ACK packet can contain acknowledgements for multiple reliable packets - just a series of `ULONG` (`unsigned long`) numbers, each representing a sequence number of a packet meant to be acknowledged.

In case no ACK is received for a packet, Serious Engine will attempt retransmission several times before closing the (virtual) connection to the client, and this is kept track of in `pa_ubRetryNumber`. Number of retries is specified with shell variable `net_iMaxSendRetries` and can be configured via console or configuration files. It seems to be `10` by default. It is worth noting that each retransmission will delay the next one by a certain amount of time. This is also configurable with shell variable `net_fSendRetryWait`, which seems to be `0.5f` by default. Each retransmission can occur only `net_fSendRetryWait` seconds after the previous.

`CPacket::pa_tvSendWhen` keeps track of when the packet was supposed to be sent, not including the retransmission penalty. This isn't only used to calculate when the next retry should occur, but also serves as a simple congestion control mechanism to prevent flooding the client with more messages than they can handle in a certain amount of time. Serious Engine will attempt to approximate a good time in the future to send a particular packet based on the packet size, bandwidth limit, latency limit and latency variation. The latter two are used to simulate real network conditions and are configurable via shell variables (I believe this was only intended for debugging), while the bandwidth limit configuration is also exposed in the options menu:

![Banner](/img/articles/serious-engine/network-settings.png "Network options menu.")

There options merely execute and persist shell commands in `.ini` files in `Scripts/NetSettings/`. For example, `ISDN.ini`:

    cli_bPrediction = 1;
    cli_iBufferActions = 2;
    cli_iMinBPS = 5000;
    cli_iMaxBPS = 10000;

While prediction only affects the client, the latter three are communicated to the server upon establishing the virtual connection as `CSessionSocketParams`.

    class CSessionSocketParams {
    public:
        INDEX ssp_iBufferActions;
        INDEX ssp_iMaxBPS;
        INDEX ssp_iMinBPS;
    }

This allows the server to work with clients with varying connection speeds and quality. Packet time is approximated in `CPacketBufferStats::GetPacketSendTime`.

As for the rest of the `CPacket` fields, `CPacket::pa_slSize` represents the size of packet payload in bytes, while `CPacket::pa_slTransferSize` represents the size of the stream payload in bytes. In case the packet isn't part of a stream, these fields are equal.

These packets are the basics for higher-level constructs such as `CNetworkMessage`, which we'll cover soon. But first, let's take a look at how the packets are used in a real multiplayer session.

### The Lifecycle of a Connection <a name="the-lifecycle-of-a-connection"></a>

`CCommunicationInterface` is the main class responsible for packet-layer communication. Among mostly uninteresting socket abstraction and handling, we have three sets of distinct member functions:

    // Send an unreliable packet to the specified client.
    void Server_Send_Unreliable(INDEX iClient,
                                const void *pvSend,
                                SLONG slSendSize);

    // Check if any unreliable packets have arrived from
    // the specified client. If so, fill out the buffer
    // and the size and return true.
    BOOL Server_Receive_Unreliable(INDEX iClient,
                                   void *pvReceive,
                                   SLONG &slReceiveSize);

    // Also: reliable variation.

And these:

    // Send an unreliable packet to the server.
    void Client_Send_Unreliable(const void *pvSend, SLONG slSendSize);

    // Check if any unreliable packets have arrived from the server.
    // If so, fill out the buffer and size and return true.
    BOOL Client_Receive_Unreliable(void *pvReceive, SLONG &slReceiveSize);

    // Also: reliable variation.

But also these:

    // Sends a packet to a specified CAddress.
    void Broadcast_Send(const void *pvSend,
                        SLONG slSendSize,
                        CAddress &adrDestination);

    // Check if there are any packets from any address.
    // If so, fill out the buffer, size and address and
    // return true.
    BOOL Broadcast_Receive(void *pvReceive,
                           SLONG &slReceiveSize,
                           CAddress &adrAddress);

>**NOTE:** If you find the above naming confusing, perhaps it'll help if you think of this as a polymorphic class, with derived classes like `CServerCommunicationInterface`, `CClientCommunicationInterface` and `CBroadcastCommunicationInterface`. But hey, static calls beat polymorphic indirection.

Notice how the server and the client interfaces both assume the source or destination of the message is already known. In other words, it's assumed that the virtual connection between the client and the server is already established. However, if you look at the **broadcast interface**, you'll see that these methods can send and receive packets to and from **any** address - this is used to establish the connection. To understand how this works, we need to explore the concept of **master buffers** and **packet routing**.

### Master Buffers <a name="master-buffers"></a>

`CCommunicationInterface` has two main (master) packet buffers - one for input, and one for output. Every time the Engine calls `CCommunicationInterface::UpdateMasterBuffers()`, the communication interface will do the following:

1. Poll the socket API (Winsock) to check for and read any incoming UDP packets, deserialize them into `CPackets` and insert them into the master input buffer (`cci_pbMasterInput`).
2. Serialize and send out (via socket API) any `CPackets` in the master output buffer (`cci_pbMasterOutput`).

Notice how this is very simple - UDP layer is very thin, and all the heavy lifting is done on the higher levels.

### Packet Routing <a name="packet-routing"></a>

This is where things get more interesting. Remember the three interface groups from `CCommunicationInterface`? They each actually just call the (mostly) same functions of a corresponding `CClientInterface`.

    CClientInterface cm_aciClients[SERVER_CLIENTS];
    CClientInterface cm_ciBroadcast;
    CClientInterface cm_ciLocalClient;

The purpose of `CClientInterface` is to abstract away the complexity of communicating with a client (or the server, if used by the client). When the application is the server, `cm_aciClients` array is used to provide an interface for each player in the game. If the application is the client, it uses `cm_ciLocalClient` to communicate with the server. `cm_ciBroadcast` is used by both the client and the server to establish the connection.

![Communication Interface](/img/articles/serious-engine/comminterface.png "Communication Interface")

`CClientInterface` contains simple methods by design:

    // Sends a message through the interface.
    void Send(const void *pvSend, SLONG slSize, BOOL bReliable);

    // Broadcast variant.
    void SendTo(const void *pvSend,
                SLONG slSize,
                const CAddress adrAdress,
                BOOL bReliable);

However, the implementation is a bit more complex. Internally, `CClientInterface` performs packet ordering and reliability. For this purpose, it contains four main buffers.

    CPacketBuffer ci_pbOutputBuffer;
	CPacketBuffer ci_pbWaitAckBuffer;
	CPacketBuffer ci_pbInputBuffer;
	CPacketBuffer ci_pbReliableInputBuffer;

For now, let's focus on `ci_pbInputBuffer` and `ci_pbOutputBuffer`. As you may have guessed, these are the input and output packet buffers. Input buffer contains packets which were meant to be received by this client interface, and output buffer contains packet which are meant to be sent by this interface. But how do packets end up in `ci_pbInputBuffer`, and get out of `ci_pbOutputBuffer`?

They actually come from the `CCommunicationInterface`'s input master buffer, and end up in its output master buffer, but how does the Engine know which `CClientInterface` needs to receive a certain packet?

Packet routing!

If you go back a bit and look at the `CPacket` structure, you'll see it contains a `CAddress` object (`pa_adrAddress`). Let's have a look what this actually is.

    class CAddress {
    public:
        ULONG adr_ulAddress;   // IPv4 address.
        UWORD adr_uwPort;      // UDP port.
        UWORD adr_uwID;        // Huh?
    }

`adr_uwID`, depending on its value, may carry either:

- unique identifier for a client
- information that this is a broadcast packet

If `adr_uwID` is equal to `'//'` (`0x2f2f`) or `0`, this packet was meant for, or came from the broadcast interface. Otherwise, it contains a unique client ID for this session.

So, if the packet is a broadcast packet, it's routed to the broadcast interface, otherwise it is routed to the corresponding client interface. You can see the routing logic performed in `Server_Update` and `Client_Update` methods of `CCommunicationInterface`.

### Establishing a connection <a name="establishing-a-connection"></a>

In order to connect to the server, the client must send a reliable broadcast packet with the `UDP_PACKET_CONNECT_REQUEST` flag. We can see this in `CCommunicationInterface::Client_OpenNet_t`:

    // Instantiate the connection request packet.
	ppaInfoPacket = new CPacket;

    // Set the flags.
	ubReliable = UDP_PACKET_RELIABLE
                 | UDP_PACKET_RELIABLE_HEAD
                 | UDP_PACKET_RELIABLE_TAIL
                 | UDP_PACKET_CONNECT_REQUEST;

    // Set parameters and write a single-byte (useless) payload.
	ppaInfoPacket->pa_adrAddress.adr_ulAddress = ulServerAddress;
	ppaInfoPacket->pa_adrAddress.adr_uwPort = net_iPort;
	ppaInfoPacket->pa_ubRetryNumber = 0;
	ppaInfoPacket->WriteToPacket(&ubDummy,
                                 1,
                                 ubReliable,
                                 cm_ciLocalClient.ci_ulSequence++,
                                 '//',
                                 1);

When the server receives this packet, it will first check whether the client with this address and port (from which the packet came from) is already connected. If so, the packet is simply ignored. If not, the server will look for the first empty client interface and do the following:

1. Generate the unique identifier for that client and assign it to the corresponding `CClientInterface`.
2. Send the unique identifier to the client via the `UDP_PACKET_CONNECT_RESPONSE` reliable broadcast packet.

Identifier generation is pretty straightforward:

    // This isn't some cryptographic hash so the timer value will do.
    UWORD uwID = _pTimer->GetHighPrecisionTimer().tv_llValue & 0x0FFF;

    // In case we're so unlucky we hit a broadcast packet marker,
    // just increment by one.
    if (uwID==0 || uwID=='//') {
        uwID+=1;
    }

    // Assign the ID to the client interface.
    cm_aciClients[iClient].ci_adrAddress.adr_uwID = (uwID<<4)+iClient;

From the moment the server sends the response packet, the client is considered connected. The client will then use the provided `uwID` to identify themselves when sending packets to the server, and the server will properly route the packet to the corresponding client interface.

Why bother with `uwID`, though? Why not just assign an index?

It prevents impersonation attacks. The attacker would need to guess `uwID` of the player they would want to impersonate, so the attack surface is lowered. Sure, they could brute-force the `uwID` by spamming non-broadcast packets and receive an ACK at some point as confirmation, but that wouldn't be very subtle - non-broadcast packets from non-connected players will cause Serious Engine to emit a warning in the console. You can see this in `CCommunicationInterface` method `Server_Update`.

    // bClientFound - true if packet came from connected client.
    if (!bClientFound) {
        // warn about possible attack
        extern INDEX net_bReportMiscErrors;
        if (net_bReportMiscErrors) {
            CPrintF(TRANS("WARNING: Invalid message from: %s\n"),
                AddressToString(ppaPacket->pa_adrAddress.adr_ulAddress));
        }
    }

### Reliability <a name="reliability"></a>

Let's head back to the `CClientInterface` and have a look at these buffers again.

    CPacketBuffer ci_pbOutputBuffer;
	CPacketBuffer ci_pbWaitAckBuffer;
	CPacketBuffer ci_pbInputBuffer;
	CPacketBuffer ci_pbReliableInputBuffer;

`ci_pbWaitAckBuffer` is the buffer containing copies of reliable packets which have been sent. In case the Engine doesn't receive the ACK for these, it will attempt retransmission. The packets are copied into this buffer from `ci_pbOutputBuffer` before being sent into the master output buffer.

`ci_pbReliableInputBuffer` contains ordered and deduplicated reliable packets. It's filled just after the packets are routed to the `ci_pbInputBuffer` from the master input buffer. The Engine iterates through packets in `ci_pbInputBuffer` and does several things:

1. If the incoming packet is an ACK packet, remove the acknowledged packets from both `ci_pbWaitAckBuffer` and `ci_pbOutputBuffer`. Also remove the ACK packet from the input buffer.
2. If the incoming packet is reliable, then insert it into `ci_pbReliableInputBuffer`, but only if not already present (deduplication). Also remove the packet from the input buffer, and write it up for acknowledgement.
3. If the incoming packet is unreliable, leave it in the input buffer.
4. Generate an ACK packet (or packets) which contain acknowledges for each of the input packets written up for acknowledgement.

It's a simple but elegant system.

### Offline Play <a name="offline-play"></a>

The singleplayer and demo reproduction are just a special case of multiplayer. We still have the server, and still have the client, but here they're the same process.

It would be somewhat ridiculous to use the network sockets to communicate with something in the same process, so the Engine establishes a simple shortcut. If we observe `CCommunicationInterface`, we can see this:

    void CCommunicationInterface::Client_OpenLocal(void)
    {
        CTSingleLock slComm(&cm_csComm, TRUE);

        CClientInterface &ci0 = cm_ciLocalClient;
        CClientInterface &ci1 = cm_aciClients[SERVER_LOCAL_CLIENT];

        ci0.ci_bUsed = TRUE;
        ci0.SetLocal(&ci1);
        ci1.ci_bUsed = TRUE;
        ci1.SetLocal(&ci0);
    };

`ci0` is the virtual client's `CClientInterface`, and `ci1` is the matching `CClientInterface` as it would be on the server. These client interfaces become paired in `CClientInterface::SetLocal`:

    void CClientInterface::SetLocal(CClientInterface *pciOther)
    {
        // ...
        ci_pciOther = pciOther;
        // ...
    }

When two client interfaces are paired, they can exchange buffers by calling `CClientInterface::ExchangeBuffers`. This will consume packets from one interface's output buffer and insert them into the other interface's input buffer, then vice versa. This eliminates the need for sending and receiving everything through master output and input buffers when playing locally.

Buffer exchange is performed in `CCommunicationInterface::Server_Update`.

And that pretty-much covers the packet layer overview.

There's a bit more going on in there than I laid out, but I suggest you consult the source code if you want to know more. After all, this is a conceptual overview, so I'd rather not bore the average reader to death with details.

`CPackets` provide a neat layer above the UDP, but they're still somewhat low-level and awkward to use, at least directly. This is why Croteam introduced another layer above packets - **network messages**.

## The Message Layer <a name="the-message-layer"></a>

`CNetworkMessage` is a message abstraction which can be read from and written into in a stream-like manner. Let's look at the data members:

    class ENGINE_API CNetworkMessage {
    public:
        MESSAGETYPE nm_mtType; // Message type (enumeration).

        #define MAX_NETWORKMESSAGE_SIZE 2048
        UBYTE *nm_pubMessage;  // Buffer (allocated on heap).
        SLONG nm_slMaxSize;    // Buffer size.

        UBYTE *nm_pubPointer;  // Read/write pointer.
        SLONG nm_slSize;       // Message size (so far).
        INDEX nm_iBit;         // Next bit index to read/write.

        // ...
    };

I was surprised to find that `nm_pubMessage` is allocated via `AllocMemory` which seems to just call `malloc` under the hood. In fact, memory is allocated this way all over the Engine. There's a `CLinearAllocator`, but doesn't seem to be used anywhere. `CNetworkMessage` buffers are allocated (and reallocated) quite often, so at some point, some people would argue that the heap could end up looking like swiss cheese.

Well, it's either that, or I missed a custom allocator implementation somewhere within the Engine codebase. But then again, it's not like you'd need a long-running server for this kind of game, so you probably wouldn't even notice; heap fragmentation usually becomes a problem when software is expected to work for days or even weeks.

`CNetworkMessage` is meant to be written into and read from via simple interface:

    void Read(void *pvBuffer, SLONG slSize);
    void Write(const void *pvBuffer, SLONG slSize);
    void ReadBits(void *pvBuffer, INDEX ctBits);
    void WriteBits(const void *pvBuffer, INDEX ctBits);

but also like a stream:

    inline CNetworkMessage &operator>>(SLONG &sl);
    inline CNetworkMessage &operator>>(SWORD &sw);

    // ...

    inline CNetworkMessage &operator<<(const SLONG &sl);
    inline CNetworkMessage &operator<<(const SWORD &sw);

    // ...

    void Rewind(void);

Messages can also contain submessages (serialized version of themselves). Once the message buffer contains all the data needed, the buffer can be reallocated to fit the data (`CNetworkMessage::Shrink`).

### Message Compression <a name="message-compression"></a>

It's also worth noting that messages can be compressed by either specifying a `Compressor` or using the default one based on `nm_mtType`. The enumeration (`MESSAGETYPE`) is actually just the lower 6 bits, while the remaining two indicate a type of compression used. This can be either:

- LZ77 (`CzlibCompressor`)
- LZRW1 (`CLZCompressor`)
- uncompressed

LZRW1 seems to be used by default. This can be changed via shell variable `net_iCompression`, most likely just for development purposes.

Also, remember `CPlayerAction` from the beginning of the article? If we peek into `PlayerBuffer::CreateActionPacket`, we can see this piece of code:

    CPlayerAction paDelta;
    for (INDEX i=0; i<sizeof(CPlayerAction); i++) {
        ((UBYTE*)&paDelta)[i] = ((UBYTE*)&paCurrent)[i]
                                ^ ((UBYTE*)&plb_paLastAction)[i];
    }

The `CPlayerAction` here is being prepared for sending, but the structure itself isn't being sent, but rather its *delta*, which is just a result of a XOR operation between the current and the last player action sent.

Then again, in `PlayerTarget::ApplyActionPacket`, which is meant to be processed by the receiving end, we can see this:

    for (INDEX i=0; i<sizeof(CPlayerAction); i++) {
        ((UBYTE*)&plt_paLastAction)[i] ^= ((UBYTE*)&paDelta)[i];
    }

The `CPlayerAction` is being XOR-ed back, yielding the desired player action. But why go through all this trouble? Why not just send the `CPlayerAction`, thus avoiding calculating the delta and reconstructing the action structure?

Because a **delta can be compressed more efficiently** when the data hasn't changed much.

And in this particular case, data really doesn't change that much; for example, `CPlayerAction` contains information about keys being held down, and players often hold the same keys for a period over several frames, so it makes sense to minimize the amount of information being sent over the network (or being written to a file). Same goes for velocity and view rotation - they don't cover the full range of the floating point, so there's usually very little change there.

We might not see the benefit of this when sending a single client action (e.g. from client to server), but rather when they're being sent in bulk, as server does via `MSG_SEQ_ALLACTIONS`.

Neat trick, huh? It's actually a well-known and established concept called [delta encoding](https://en.wikipedia.org/wiki/Delta_encoding).

### Message Security <a name="message-security"></a>

Messages aren't encrypted. Most people would agree that observing a way someone dodges a Kleer or a Sirian Werebull is hardly a meaningful privacy violation.

However, that may not be true for chat messages.

If we put on our tinfoil hat and disable message compression:

    /net_iCompression=0

By sending a chat message in-game, we can see the UDP packet and its payload. Since it's transmitted in plaintext, we can see the whole message.

![Wireshark output](/img/articles/serious-engine/wireshrek.png "Wireshark output")

Sure, in real-case scenario, the compression would be enabled and someone sniffing for UDP packets would have to go through the trouble of figuring out this is a LZ-compressed stream and then decompress it, but they'd have everything they need in order to do it.

So yeah - the original Serious Sam multiplayer sessions might not be the best place to have very private conversations. But then again, it's not like people play this game to *slide into DMs*.

This isn't anything controversial or particularly concerning, though - most games from that time didn't deal with encryption simply because it wasn't necessary, or would perhaps increase complexity since it would require implementing mechanisms like authentication and key exchange.

Also, at the time, most of the web was still on HTTP.

### Message Dispatcher <a name="message-dispatcher"></a>

`CMessageDispatcher` is essentially a wrapper around the packet layer.

It invokes `CCommunicationInterface`'s functions to send packets with the `CNetworkMessage`'s content, or receive a `CNetworkMessage` by reading the packet content.

Its job is also to prepare the `_cmiComm` (global `CCommunicationInterface`) for use based on the selected `CNetworkProvider`. This is actually just a description wrapper, and can be:

- `Local`
- `TCP/IP Server`
- `TCP/IP Client`

"Preparation for use" here is basically just deciding whether to open the socket and how to open it.

- `Local` is used when playing singleplayer or the demo recording. Winsock isn't initialized here, so no socket either.
- `TCP/IP Server` is used when hosting. The socket is opened on the port specified by `net_iPort` shell variable.
- `TCP/IP Client` is used when we're the client. It also opens the socket, but the Engine lets the socket API decide on the port, since it doesn't matter.

## The Game Session Layer <a name="the-game-session-layer"></a>

To see network messages in action, let's take a step back and get a bit broader look at how Serious Engine manages a multiplayer game. We'll skip the outer layers dealing with platform specifics, timing and rendering, and just focus on game logic and communication, and that's mostly packed in `CNetworkLibrary`.

A seemingly unusual place for game logic, isn't it?

`CNetworkLibrary`, despite its peculiar naming choice, is a class that houses and manages the game state (`CSessionState`), among other things. It's inherited from `CMessageDispatcher` we mentioned earlier.

The scope of `CNetworkLibrary` a bit wide and there's a lot going on there, so I'll rather attempt to simplify how the whole thing works without going into too much detail - if I start speaking in classes, this would become an unreadable mess.

### Hosting a Game <a name="hosting-a-game"></a>

Let's assume we want to start a server. Upon hosting the game (`CNetworkLibrary::StartPeerToPeer_t()`), the Engine will do the following:

1. Initialize CRC (cyclic redundancy check) gathering. This is used later to determine whether the connecting clients have the same files as the server. This isn't a cheat prevention method, but rather a way to detect desynchronization early.
2. Create a new session state (`CSessionState`), serialize it and store it into `ga_pubDefaultState`. This is considered the default state and will be used as a baseline for calculating **state deltas** later on.
3. Load the local world instance.
4. Initialize the global communication interface.
5. Set up and initialize the local session state (`ga_sesSessionState`). When clients connect, they will receive a **state delta** - a difference between the default (baseline) state and the server's local state. This is required because clients can connect to a game already in progress. The local client is also initialized here (if not dedicated server).
6. Finish CRC gathering. At this point CRC of files is stored in `ga_ulCRC`. When clients connect, they will request a list of filenames to check (`MSG_REQ_CRCLIST`). The server will then send a list of filenames (`MSG_REQ_CRCCHECK`), and the client will produce a CRC of their copies of these files, then send it to the server (`MSG_REP_CRCCHECK`). If CRCs don't match, the client is disconnected.

At this point, the server is considered up and running, and we have entered the game logic loop (`CNetworkLibrary::MainLoop()`).

### Joining a Game <a name="joining-a-game"></a>

Joining a game is done via `CNetworkLibrary::JoinSession_t()`. The function receives a `CNetworkSession` parameter which contains, among various session information, a server address. This is either instantiated via polling the GameAgent (part of the engine responsible for session discovery) or manually, via the class constructor. Upon joining the game, the client will do the following:

1. Initialize CRC gathering, just like the server.
2. Set up and initialize an empty local session state.
3. Initialize the global communication interface.
5. Send a connection request message (`MSG_REQ_CONNECTREMOTESESSIONSTATE`). It contains the build version, mod name, server password, amount of local players on this client (in case of split-screen) and serialized `CSessionSocketParams` (connection quality information).
6. Wait for the response in form of `MSG_REP_CONNECTREMOTESESSIONSTATE`. It contains message of the day, world filename, spawn flags (difficulty, game mode) and session properties.
7. Initialize the baseline game state using received information (much like the server).
8. Send a `MSG_REQ_STATEDELTA` message. This requests a state delta between the baseline state (which *should* be equal on the client and the server) and the server's current local state.
9. Await a response in form of `MSG_REP_STATEDELTA`. Upon decompression, a reverse diff is performed to reconstruct the game state stream.
10. Initialize the local session state with the reconstructed stream via `CSessionState::Read_t()`.
11. Perform a CRC check with the server (`MSG_REQ_CRCLIST`/`MSG_REP_CRCCHECK`). Disconnect in case of mismatch.

At this point, the client is considered connected to the server and the Engine will enter the game loop, just like the server.

### Starting a Demo Playback <a name="starting-a-demo-playback"></a>

Demo playback is initialized via `CNetworkLibrary::StartDemoPlay_t()`. It receives a filename string as a parameter. In comparison to multiplayer, it's very simple:

1. Parse the demo file, read the header and the version.
2. Initialize `ga_sesSessionState` with the serialized game state from this point in the file stream.

At this point, the client is playing the demo and will enter the main loop.

### The Main Loop <a name="the-main-loop"></a>

The main loop is actually very similar for both the client and the server, with a few exceptions.

1. Update<sup>*</sup> the local client communication interface (`cm_ciLocalClient`) and the broadcast communication interface (`cm_ciBroadcast`).
2. Have the local session state handle the incoming network messages.
3. [`SERVER ONLY`] Exchange buffers between paired client interfaces, then update each of the server-side client communication interfaces (`cm_aciClients` array). Also update the local client and the broadcast interface again.
5. Have the local session state process its game stream.
6. [`SERVER ONLY`] Handle GameAgent update (stuff for server browser).
7. [`SERVER ONLY`] Handle remote administration shell commands, if any were sent since the last iteration.

(<sup>&ast;</sup>) *Updating a communication interface is essentially updating its four main buffers, performing message routing, etc. See packet layer section.*

`CSessionState` handles incoming network messages via `SessionStateLoop()` function. Let's look at this function more closely. It handles the following message types:

*Unreliable messages*

- `MSG_GAMESTREAMBLOCKS` - message containing game stream blocks. These are stored into the state's internal buffer to be processed later.
- `MSG_KEEPALIVE` - when received, use current time as time of session start.
- `MSG_INF_PINGS` - message containing pings of all players.
- `MSG_CHAT_OUT` - message containing a chat message.

*Reliable messages*

- `MSG_INF_DISCONNECTED` - message containing the reason why the client was disconnected.
- `MSG_ADMIN_RESPONSE` - message containing remote administration response.

For some of these messages, responses are generated right here. However, notice how `MSG_GAMESTREAMBLOCKS` is an unreliable message. But isn't this information important? **Would we not desync immediately if we miss even just one of these messages?**

We definitely would. But retransmission logic for this is handled later, when the local session state processes its game stream - `CSessionState::ProcessGameStream`. If we look into it, we can see this patch of code:

    // Calculate the index of the next expected sequence.
    INDEX iSequence = ses_iLastProcessedSequence+1;

    // Get the stream block with that sequence.
    CNetworkStreamBlock *pnsbBlock;
    CNetworkStream::Result res = ses_nsGameStream.GetBlockBySequence(iSequence,
                                                                     pnsbBlock);

Three things can happen when fetching a game stream block by sequence:

1. The block with the next expected sequence **is** found. In this case, we continue onto processing the block (`CSessionState::ProcessGameStreamBlock`).
2. The block with the next expected sequence **isn't found**, but we don't have any more recent blocks (i.e. with larger sequence number). In this case we don't do anything this iteration of the main loop.
3. The block with the next expected sequence **isn't found**, but we **already have at least one more recent block.** This means the block might have been lost, and we may have to perform retransmission.

However, there is no always need for retransmission in case of (3). The block may have simply been late due to nature of UDP. Instead of requesting retransmission immediately when we encounter a missing block, we mark this sequence as missing and set up a timeout. Then, next time the main loop ends up here and the timeout has passed, we send a retransmission request (`MSG_REQUESTGAMESTREAMRESEND`) which contains:

- the sequence of the missing block
- number of missing blocks, determined by looking up the difference between the most recent received block sequence and the missing block sequence

The server will then re-send these blocks.

Let's head over to `CSessionState::ProcessGameStreamBlock` to see how the game stream blocks actually get processed. Just to get your bearings:

    CNetworkLibrary::MainLoop();
        ga_sesSessionState.ProcessGameStream();
            ProcessGameStreamBlock(*pnsbBlock); // We're here!

Remember the game stream block types from the beginning of the article? We're finally here.

`MSG_SEQ_ADDPLAYER` is sent when a player joins the game. It contains a player index and a `CPlayerCharacter` descriptor (guid, name, team, appearance). When received, the local game session state will check whether the corresponding `CPlayerEntity` already exists in the game world - in case a player was disconnected and is reconnecting. If not, a new `CPlayerEntity` will be added to the game world. In any case, the entity becomes linked with a corresponding player target. `CPlayerTarget` is a utility class to which player actions are passed and which applies these actions to the linked player entity.

`MSG_SEQ_REMPLAYER` is sent when a player is disconnected from the game. It contains just the player index. When received, the player entity is disconnected from its player target, and the player target is deactivated.

`MSG_SEQ_CHARACTERCHANGE` is sent when a player changes an aspect of their character. It contains a player index and a `CPlayerCharacter` descriptor. The player can change their name, team or appearance. Appearance seems to be application specific - it's just a 32-byte buffer. In Serious Sam, this buffer houses a `CPlayerSettings` structure which contains the filename of the player model, weapon auto select policy, crosshair type and various flags (all customizable via in-game options menu).

`MSG_SEQ_PAUSE` is sent when the game gets paused or unpaused by someone. It contains whether the game should be paused or unpaused (`BOOL`) and a string containing the name of the player who requested the change. It affects `CSessionState::ses_bPause` - when false, the game state is not advanced, nor the player actions are being generated. When this message is received, the pauser's name is printed in the console. *As it should be.*

`MSG_SEQ_ALLACTIONS` is the most interesting of these. It contains a floating point header which represents time - this is additionally used for diagnostics, to emit a warning in case these blocks are sent too often. It's then passed to `ProcessGameTick()`, along with the rest of the message.

The time value is used as a current tick time in the local session. The session's player targets are being iterated here, and for each, the Engine deserializes a `CPlayerAction` from the message and then applies it to the player target. After the player targets are done, we have this:

    // Update timers. Generate events, etc.
    HandleTimers(tmCurrentTick);
    // Handle moving entities, physics.
    HandleMovers();

I could go into this, but I'd rather keep the scope of this tutorial limited to networking. This logic is something that everyone's local game state performs regardless of networking, and the only important thing is that everyone does it exactly the same. We have a synchronization check to confirm that:

    MakeSynchronisationCheck();

This will iterate through various objects with `ChecksumForSync()` (entities, player targets...) and produce a `CSyncCheck` object which contains the CRC with some additional info. If `CSyncCheck` is produced on the server, it's buffered.

Upon the check, `MSG_SYNCCHECK` message containing the `CSyncCheck` is sent to the server and the server disconnects the client if there's a discrepancy in relation to the server's local state.

And that's mostly it. Sure, there's a lot more going on in this loop than I covered, but then this analysis wouldn't be a short analysis anymore - let's keep it simple.

### Prediction <a name="prediction"></a>

>**NOTE:** I purposefully omitted prediction-related stuff from the main loop explanation to avoid confusion, but we'll cover the most relevant stuff here.

Did you ever hook up your PC or a videogame console to an old TV with huge HDMI input latency? You move the thumbstick and then release it, and then, half a second later, you see your character do the same. It doesn't feel very interactive.

Now imagine that, instead of TV input, we're dealing with internet latency. Let's look at a simple use-case of moving the character in a Serious Sam multiplayer session. We're a client, and we press a movement key. Assuming there's no prediction, the player action gets sent to the server, the server eventually simulates its local state and sends `MSG_SEQ_ALLACTIONS`, which contains all the player actions, including ours. The problem is, we see our character move only after the player actions have been received:

![Latency](/img/articles/serious-engine/prediction.png "Latency")

And this is the best case scenario - it becomes even worse if you take packet loss or varying network conditions into account.

**Prediction** is a mechanism which helps mitigate this a bit.

In a nutshell, prediction is just a fancy way of saying "we're going to be extrapolating because packet round-trip time makes fast-paced games feel unresponsive." In other words, the Engine will try to "guess" where the entities will be in the future without awaiting the action response from the server.

Due to the nature of Serious Engine multiplayer, it is enough to guess player actions, and the rest of the simulation will follow suit. We have two cases:

- prediction for the local player
    - the Engine will use actions sent to the server
- prediction for remote players
    - the Engine will use last received action from the server

Why even wait for player action messages from the server before simulating local state, anyway? Why not just send the action packets and proceed to simulate the world using the sent information?

Because we can't know what the other players did, and they have direct impact on the game state - we would get desynchronization. To avoid mixing the actual and the predicted game state, Serious Engine employs **predictors**.

A predictor is kind of a "ghost" entity, which is paired to a regular entity in the game world. It's essentially a copy of the entity with some special flags. There are two types of predictors:

- **Predictor** - a predictor for an existing entity in the game state.
- **Temporary predictor** - a predictor spawned during prediction. It has no linked entity, since it doesn't exist in the game state.

A **predicted entity** is an entity for which a **predictor** currently exists. When processing predicted game tick, only **predictor entities** are processed. Every time the client receives player actions from the server, the predictors are destroyed and a new prediction cycle begins.

>The nomenclature can be a bit confusing, so just to recap...
>
>- predictable entity - entity which is meant to be predicted if needed
>- predictor entity - a copy of an entity, used for prediction
>- predicted entity - a predictable entity for which a predictor exists

When rendering, **predicted** entities are not rendered - their **predictors** are rendered instead. This gives the illusion of advancing the game state, while the original game state has not changed in any meaningful way.

As for the implementation, prediction is processed just after processing the game stream.

    ga_sesSessionState.ProcessGameStream();

    // ...

    if (bUsePrediction) {
        ga_World.UnmarkForPrediction();
        ga_World.MarkForPrediction();

        ga_sesSessionState.ProcessPrediction();

        ga_World.UnmarkForPrediction();
    }

`ga_World` is a global `CWorld` instance. In `UnmarkForPrediction`, the Engine iterates through entities to be predicted and removes `ENF_WILLBEPREDICTED` flag from the entity's `en_ulFlags`. `MarkForPrediction` does the opposite - it sets the flag on any predictable entities and player entities.

A **predictable entity** is any entity with a `ENF_PREDICTABLE` flag in its `en_ulFlags`. This is typically set in a constructor of an entity class via `SetPredictable`, which also adds the entity to the world's `wo_cenPredictable` collection.

As you may have guessed, `CSessionState::ProcessPrediction` is the prediction equivalent of `CSessionState::ProcessGameStream`.

It starts by guessing how many ticks can be predicted. To understand this, let's look at `CPlayerTarget` members:

    class CPlayerTarget {
    public:
        BOOL plt_bActive;                     // True if player connected.
        CPlayerEntity *plt_penPlayerEntity;   // Linked player entity.
        CTCriticalSection plt_csAction;       // Access mutex.
        CPlayerAction plt_paPreLastAction;    // Action before last received action.
        CPlayerAction plt_paLastAction;       // Last received action.
        CActionBuffer plt_abPrediction;       // Buffer of sent actions.
        FLOAT3D plt_vPredictorPos;            // Last position of predictor.

`plt_abPrediction` is interesting in because it's a buffer of actions which were sent to the server since the last received `MSG_SEQ_ALLACTIONS`. If we sent only `N` actions, it only makes sense to predict the following `N` ticks at the most.

When the Engine knows the number of ticks to predict, it will continue to cache the RNG seed and next entity ID (to avoid corrupting the game state), and after this, delete all existing predictors and instantiate new ones (`CWorld::CreatePredictors`). Then, for each tick that can be predicted, the Engine calls `CSessionState::ProcessPredictedGameTick`.

This function is the prediction equivalent of `CSessionState::ProcessGameTick`. Functionality is similar as well - except the that we apply predicted actions to the player targets, and that we set `ses_bPredicting` to `TRUE`, which lets the game logic functions know we're currently processing prediction and not affecting the actual game state.

`CPlayerTarget::ApplyPredictedAction` is the prediction equivalent of `CPlayerTarget::ApplyActionPacket`. However, instead of action delta for the parameter, we have two things:

- `iAction` - index of the action in the `plt_abPrediction` buffer, used for local players only
- `fFactor` - interpolation factor, used for remote players only

When predicting the local player, `iAction` simply becomes the index of the prediction step (range `[0, number of predicted steps]`). Since prediction step count is capped at number of buffered actions, this is safe.

`fFactor` is a bit more interesting because it's used only when action interpolation (`cli_bLerpActions`) is enabled in the console. When predicting the remote player, we have two cases:

- if `cli_bLerpActions` is **disabled**, the predicted action is simply the last received action for that player
- if `cli_bLerpActions` is **enabled**, the predicted action is a result of linear interpolation between the last two actions received for that player

Honestly, I am not sure how enabling `cli_bLerpActions` is beneficial. Repeating the last received player action seems reasonable enough, which is likely why `cli_bLerpActions` is disabled by default.

Once the prediction ticks are processed and the prediction cycle done, RNG seed and entity ID are restored and the prediction has finished for an iteration of the main loop.

Upon rendering, the Engine will simply skip over the entities which are being predicted, and render predictors instead.

    void CRenderer::AddModelEntity(CEntity *penModel)
    {
        //...

        // Skip the entity if predicted, predicted entities should not be rendered.
        if( penModel->IsPredicted() && !gfx_bRenderPredicted) return;

# Conclusion and Additional Thoughts <a name="conclusion-and-additional-thoughts"></a>

## Comparison with Doom and Quake <a name="comparison-with-doom-and-quake"></a>

It may be interesting to compare Serious Engine's networking model to the similar shooters that came before.

For example, it's somewhat reminiscent of Doom's networking. Even though Doom was actually peer-to-peer, clients exchanged a structure similar to `CPlayerActions` and each ran their own simulation independently. Doom used a similar system [for demo recording and playback](https://doomwiki.org/wiki/Demo#Technical_information) as well. Since Doom source code was released in 1997, it may be possible that Croteam were inspired by this concept when they were developing the Serious Engine, but I'm just speculating here.

Quake, on the other hand, was much different. Instead of having each client simulate their own independent game state, the clients were "dumb" - they merely served as message relays and dind't process any significant game logic on their own, but rather received constant updates of the game state from the server. Neat thing about this concept is not having to worry about desynchronization, and the fact it's easier to prevent cheating (e.g. the server could omit sending information about entities behind walls).

Why Croteam didn't opt for this kind of networking, I can't know for sure, but I guess it has to do with the fact that Serious Sam's game sessions typically have much more active enemies and objects in the world than Quake, and thus, sending updates for that many objects each tick would likely kill the bandwidth. But as I said - I can only speculate.

## Message Portability <a name="message-portability"></a>

If you peek at the network messages, you can see some structs are being serialized with reinterpret casts. Let's consider the case of sending a synchronization check message.

    CSyncCheck sc;

    CNetworkMessage nmSyncCheck(MSG_SYNCCHECK);
    nmSyncCheck.Write(&sc, sizeof(sc)); // Oooof.
    _pNetwork->SendToServer(nmSyncCheck);

Since the developers were likely using a single compiler for all the clients, they could get away with this, but when developing a cross-platform game, this is where things get a bit slippery. The C++ standard doesn't guarantee exactly the same structure layout across different compilers. Compilers may insert padding bytes to align members for faster access, and this padding may vary, so in the end, the resulting structs could end up different.

E.g. when compiling a 32-bit executable, the compiler might attempt to align members to 4-byte boundary, and 8-byte boundary for 64-bit executables.

There's also the matter of endianness as well (e.g. x86 PC is little-endian, PS3 is big-endian).

But again - the luxury of having a single compiler and developing for a single platform basically made these issues go away.

## Final Thoughts <a name="final-thoughts"></a>

To recap, Serious Engine is an interesting example of a well-thought-out architecture in regard to multiple game modes. The system is fairly elegant since it abstracts away the specifics of the transport medium, be it network or a file, from the game logic.

Due to the nature of the multiplayer model in which everyone maintains a copy of the game state, cheating is possible - for example, it's possible to create a hacked client which would display outlines of other players behind walls, and thus gain an advantage in deathmatch. But let's be honest here - no one plays this game for the deathmatch, most of the people are here for the co-op.

This was an interesting experience which gave me some pretty good ideas to experiment with and possibly incorporate into my hobby games. Tearing apart other people's work to see how it ticks seems like a good way to learn a thing or two.

Once again, do keep in mind that I barely scratched the surface here - I didn't even cover the entirety of networking, only the parts I found most interesting. There's much to be said about the other parts of the Serious Engine, but this could be a topic for another time. Even this article came out longer than I originally intended!

If you liked the writeup, consider [following me on Twitter](https://twitter.com/Sklopec).

Until next time!