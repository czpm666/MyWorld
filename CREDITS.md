CREDITS
=======

Attribution for third-party assets used by this project.

Each asset keeps **its own original license**. The repository's own `LICENSE`
(PolyForm Noncommercial 1.0.0, code) and the CC BY-NC-SA 4.0 content license
do **not** replace or relicense anything listed below.

Summary
-------

| Asset | Author | License | Attribution required? |
|---|---|---|---|
| **KayKit : Adventurers Character Pack (1.0)** | **Kay Lousberg** — https://www.kaylousberg.com | **CC0 1.0** — https://creativecommons.org/publicdomain/zero/1.0/ | **No** (voluntary credit appreciated) |
| *Fantasy SFX Pack Vol. 1* | *JC Sounds* | *CC BY 4.0* | **Yes** |

> ⚠️ The sound-effect entries are **pending**: their file/author/license fields are
> recorded as the sounds are actually downloaded and wired in
> (see `docs/artifacts/T-063/sfx-selection.md`). Until then, the row above is a
> **placeholder and must not be treated as final**.


KayKit : Adventurers Character Pack (1.0)
------------------------------------------

* **Author / distributor:** Kay Lousberg (https://www.kaylousberg.com)
* **Pack name:** KayKit : Adventurers Character Pack (1.0)
* **Creation date (per bundled `LICENSE.txt`):** 2023-03-13
* **License:** **Creative Commons Zero (CC0 1.0)** — public domain dedication
  <https://creativecommons.org/publicdomain/zero/1.0/>
* **Source:** bundled with the project at
  `Assets/ThirdParty/KayKit_Adventurers/`, whose own `LICENSE.txt` states, verbatim:

  > License: (Creative Commons Zero, CC0)
  > http://creativecommons.org/publicdomain/zero/1.0/
  >
  > This content is free to use in personal, educational and commercial projects.
  >
  > Support me by using a brand resource provided in this pack or by crediting
  > Kay Lousberg, www.kaylousberg.com (**this is not mandatory**)

* **Attribution required?** **No.** CC0 does not require attribution, and the bundled
  license text explicitly calls crediting *"not mandatory"*.
  **It is listed here anyway, for clarity and out of courtesy to the author** —
  so that anyone asking *"which assets require attribution?"* can see the answer at a
  glance and tell the two groups apart.

**How it is used in this project:**
* The player character model and animations (the "Mage").
* The enemy character model and animations (the "Barbarian").
* Several weapon meshes (sword, staff, crossbow used as the bow, round shield).


Sound effects
-------------

### JC Sounds — *Fantasy SFX Pack Vol. 1*  *(planned — asset not yet obtained)*
* **License:** **CC BY 4.0** — <https://creativecommons.org/licenses/by/4.0/>
* **Attribution: REQUIRED** (CC BY 4.0 obliges credit).
* **Planned use:** the bow-release sound (slot reserved in `GameAudio.bowShotClip`, currently **empty**).
* **Status:** **asset not yet downloaded** (source transfer stalled) — this row is a
  **planned use**, not a shipped one. It will be finalized (exact file name, source URL)
  when the asset lands. See `docs/artifacts/T-063/sfx-selection.md`.
* **Required credit line** (author/pack/license per the source page — recorded verbatim):
  > Sound effects from *Fantasy SFX Pack Vol. 1* by **JC Sounds**, licensed under CC BY 4.0.

### CC0 sound packs — **in use** (attribution not required; listed anyway)

Three sounds are shipped. All three are **CC0 1.0** → **no attribution obligation**, and the
bundled license of the KayKit pack likewise calls crediting *"not mandatory"*.
**They are listed here anyway, for clarity** — so that anyone asking *"which assets require
attribution?"* can tell the two groups apart at a glance.

| Sound (in-game use) | File in project | Pack | Author | License |
|---|---|---|---|---|
| **Sword swing** | `Assets/Audio/sfx_swing_swish-9.wav` | Swishes Sound Pack | **artisticdude** | **CC0 1.0** |
| **Hit (sword/arrow/spell)** | `Assets/Audio/sfx_hit_bfh1_hit_04.ogg` | 75 CC0 breaking / falling / hit sfx | **rubberduck** | **CC0 1.0** |
| **Player hurt** | `Assets/Audio/sfx_hurt_playerhit_0.mp3` | Player Hit (damage) | **GreyFrogGames** | **CC0 1.0** |

* **License:** **CC0 1.0 (public domain dedication)** —
  <https://creativecommons.org/publicdomain/zero/1.0/>
* **Source:** OpenGameArt.org direct links (no login). Full URLs and the selection
  rationale are recorded in `docs/artifacts/T-063/sfx-selection.md`.
* **Attribution required?** **No.** Listed for clarity only.

### Spellcast sound — **no asset yet**
The spellcast slot (`GameAudio.castClip`) is **empty by design**. The originally planned
CC0 pack ("80 CC0 RPG SFX" by *rubberduck*, CC0 1.0) is still transferring.
**No substitute synthetic/placeholder sound was added** — an empty slot is clearly better
than an unattributed one.


Notes
-----

* **Attribution accuracy matters**: a wrong or partial credit does not satisfy
  CC BY. The author name, pack name, license name and source link for the CC BY
  asset are therefore recorded verbatim from its source page when downloaded.
* **This file must not be treated as complete** while the entries above are marked
  pending.
