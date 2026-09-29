# My World

A **2.5D top-down action game** built in Unity, with a **toy-diorama** look
(tilted perspective camera, chunky low-poly shapes, solid-colour materials).

You play a mage in a small walled world, carrying **six weapons** — a staff, a
sword, a bow, a grappling hook, a shield and a magic gauntlet — and fight a melee
enemy that uses telegraphed attacks.

> **Status: an early work-in-progress prototype.** The core combat loop runs, but
> most art and all audio are still placeholders. See *Current state* below for an
> honest list of what is and is not done.

---

## How to open it

1. Install **Unity 6000.3.0b1** (with the **URP** 3D template support).
2. Open this folder (`E:\My World` or wherever you cloned it) as a Unity project.
   > The repository deliberately excludes `Library/`, `Temp/`, `Logs/`, `UserSettings/`
   > and IDE project files — Unity regenerates those on first open. The first import
   > will take a while.
3. Open the scene **`Assets/Scenes/MyWorld.unity`**.
4. Press **Play**.

> ⚠️ The game generates its animation clips and animator controllers through editor
> scripts under `Assets/Editor/` (menu **`Tools → My World`**). Those generated assets
> **are** committed, so a fresh clone plays immediately — you only need the menu if
> you want to regenerate them.

---

## Controls

| Input | Action |
|---|---|
| **WASD** | Move (8-directional) |
| **Shift** | Sprint |
| **Space** | Jump |
| **Left mouse** | Use the weapon in the active hand |
| **Right mouse** | Use the off-hand weapon (hold: shield block / grappling hook) |
| **Q** | Lock on / off |
| **Tab** | Open the menu (backpack / weapons / character / settings) |
| **Esc** | Jump straight to settings |

The camera's yaw is **fixed at 0** (screen-up is world +Z). This is deliberate: WASD
maps directly to world directions and the character snaps to 8 facings, which only
holds if the camera never rotates.

---

## Current state

**Working**

- World generation, baked into the scene at edit time (walls, ground, trees, rocks, houses, lighting)
- 8-direction movement, jumping, sprinting
- **Sword: a four-hit combo** — horizontal chop → downward chop → diagonal slash → thrust.
  Damage, knockback and the slash VFX are all driven by an **animation event** on the
  swinging frame, so the hit always lines up with the animation
- **Bow:** the arrow is released by an animation event, not on the key press
- Staff spell projectiles, homing aim when a target is locked
- Grappling hook (pull yourself or pull the target)
- Shield blocking + shield bash; magic gauntlet as a casting buff
- Enemy AI with four telegraphed attacks, hit-stun with a cooldown, knockback
- Menu UI built entirely in code at runtime (no UI asset files)
- Depth-of-field / diorama post-processing (configurable)

**Not done / placeholder**

- **Art is placeholder** — primitive shapes and flat colours; the character and enemy
  models are third-party low-poly assets (see `CREDITS.md`)
- **Audio: none yet.** A small set of sound effects (swing, hit, bow release,
  spellcast, player hurt) is planned; there is no music and none is planned
- No save/load, no level progression, no menus beyond the in-game one
- No builds are provided; this is a source-only prototype

---

## Layout

```
Assets/
  Editor/           one-click setup scripts (character, enemy, weapons, world baking)
  Scripts/MyWorld/  runtime gameplay code
  ThirdParty/       third-party assets (see CREDITS.md)
  Scenes/           MyWorld.unity — the playable scene
  Generated/        assets produced by the world-baking step
ProjectSettings/    Unity project settings
```

---

## Licensing

This repository uses **different licenses for different kinds of content** —
please read `NOTICE` as well as `LICENSE`.

| Content | License |
|---|---|
| **Source code** | **PolyForm Noncommercial License 1.0.0** — see `LICENSE` |
| **Project content** — documents, world/map data, original configuration and original artwork made for this project | **CC BY-NC-SA 4.0** — <https://creativecommons.org/licenses/by-nc-sa/4.0/> |
| **Third-party assets** | **their own original licenses** — see `CREDITS.md` |

**This is a non-commercial project.** You may read, download, run, modify and
redistribute the code for **non-commercial** purposes; if you pass it on you must
also pass along the license terms and keep the `Required Notice:` line.

> ⚠️ **Scope, stated plainly:** **PolyForm Noncommercial has no ShareAlike clause.**
> So others **may** make **closed-source non-commercial** derivatives of the *code*,
> as long as they keep the `Required Notice:` line. The code license is **not
> copyleft/"viral"**. ShareAlike applies only to the CC BY-NC-SA 4.0 *content*.
> (A classic copyleft license such as the GPL cannot be combined with a
> non-commercial restriction, which is why it is not used here.)

`NOTICE` also covers the project's unofficial, unaffiliated status and the
take-down policy.
