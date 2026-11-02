using System.Collections.Generic;
using UnityEngine;
using MyWorld.Kingdom;

namespace MyWorld.Maps
{
    /// <summary>
    /// The Asura capital "Ars": a whole city built in Blender (walls / inner city / castle /
    /// cathedral / guild / market / harbour / city blocks / suburbs), imported as 11 part FBX
    /// prefabs and re-assembled at the world origin at Play time.
    ///
    /// Key fact: the vertices inside these parts are ALREADY in world coordinates in Blender (the
    /// transform was applied before export), so every part can be merged with an identity transform
    /// at (0,0,0) - never offset or scale the individual parts, and never touch the localScale /
    /// localRotation of the FBX root node (Unity relies on that 270 degree X node to turn Z-up into
    /// Y-up).
    ///
    /// Collision: the FBX has the automatic colliders removed (hundreds of mesh colliders would drag
    /// the physics down), so an invisible ground plate is laid here to hold the player.
    /// </summary>
    public class AsuraCapitalMap : MapBootstrap
    {
        [Header("Capital parts")]
        [Tooltip("ars_ground / ars_walls / ars_gates / ars_inner / ars_castle / ars_cathedral / ars_guild / ars_market / ars_harbour / ars_city / ars_suburbs")]
        public GameObject[] capitalPrefabs;

        [Header("Street frontage")]
        [Tooltip("kit house_a..house_f, used to fill the gaps between the imported city blocks (the Capital menu fills this automatically)")]
        public GameObject[] housePrefabs;

        [Tooltip("How many street-front houses to add; 0 = add none")]
        public int streetHouses = 380;
        public GameObject[] propPrefabs;
        public int propCount = 220;

        /// <summary>
        /// Each part must be rotated -90 degrees X as a whole to be "upright": after import the
        /// vertices are still in Blender's original space (height on the Z axis) and the 270 degree X
        /// node inside the prefab has no effect. The symptom: the whole city looked like a wall picture
        /// standing up, houses floating, birds-eye shots all showing a top plane.
        /// The extra 180 degrees Y makes the south gate face -Z, so the default camera (looking at +Z)
        /// looks into the city from the moment it spawns.
        /// </summary>
        private static readonly Quaternion PieceRotation =
            Quaternion.Euler(0f, 180f, 0f) * Quaternion.Euler(-90f, 0f, 0f);

        // The city gate is the south gate at z=-300. The spawn point sits 60 m inside, in the middle
        // of the main street: it used to be -284 (16 m inside the arch), where the top-down camera is
        // 14.8 m behind and 19 m up, i.e. looking straight through the 30 m deep gate block - 92.5% of
        // the frame filled with one stone wall (measured). At -240 the player really is on the street.
        private static readonly Vector3 SouthGateSpawn = new Vector3(0f, 0.2f, -240f);

        [Header("Capital atmosphere")]
        public float fogStart = 800f;
        public float fogEnd = 4200f;

        protected override void BuildEnvironment(Transform world)
        {
            // The visual ground lives in the ars_ground part; only collision is added here.
            var root = new GameObject("Collision").transform;
            root.SetParent(world, false);
            var floor = GameObject.CreatePrimitive(PrimitiveType.Cube);
            floor.name = "InvisibleFloor";
            floor.transform.SetParent(root, false);
            // The top face must be at y=0: it used to be a 1 m cube at y=-0.6, so the top sat at -0.1
            // and the measured player foot after entering the scene was -0.07 - 10 cm below the Blender
            // ground, so the feet sank into the paving.
            floor.transform.position = new Vector3(0f, -0.5f, 0f);
            floor.transform.localScale = new Vector3(760f, 1f, 760f);
            var mr = floor.GetComponent<MeshRenderer>();
            if (mr != null) mr.enabled = false;
            var col = floor.GetComponent<BoxCollider>();
            if (col != null) col.isTrigger = false;
        }

        protected override void BuildMapContent(Transform world)
        {
            var root = new GameObject("Capital").transform;
            root.SetParent(world, false);

            int placed = 0;
            long tris = 0;
            if (capitalPrefabs != null)
            {
                for (int i = 0; i < capitalPrefabs.Length; i++)
                {
                    var prefab = capitalPrefabs[i];
                    if (prefab == null)
                    {
                        Debug.LogWarning("[AsuraCapital] part " + i + " is empty (the Capital menu was never filled in?)");
                        continue;
                    }
                    var go = Instantiate(prefab, Vector3.zero, PieceRotation, root);
                    go.name = prefab.name;
                    placed++;
                    var mfs = go.GetComponentsInChildren<MeshFilter>(true);
                    for (int m = 0; m < mfs.Length; m++)
                    {
                        var mesh = mfs[m].sharedMesh;
                        if (mesh != null) tris += mesh.triangles.Length / 3;
                    }
                }
            }
            else
            {
                Debug.LogError("[AsuraCapital] capitalPrefabs missing; run menu Kingdom 1 to import the FBX");
            }

            BuildAtmosphere(world);
            BuildGatePortal(world);
            BuildPeople(root);
            BuildSurfacePaving(root);   // pave first, buildings press on top of it
            DressStreets(root);
            BuildProps(root);

            Debug.Log("[AsuraCapital] parts " + placed + " / triangles " + tris +
                      " / spawn " + SouthGateSpawn);
        }

        protected override void BuildSystems(Transform world)
        {
            // Weather: clear day by default, 06:20 morning light; the menu can switch to rain / snow /
            // storm.
            if (GetComponent<KingdomWeather>() == null)
            {
                var w = gameObject.AddComponent<KingdomWeather>();
                w.weather = SkyWeather.Fair;
                w.hourOfDay = 8.4f;
            }

            // City minimap: ring road + eight radial avenues + castle / market / cathedral / guild /
            // harbour.
            if (GetComponent<MinimapHud>() == null)
            {
                var hud = gameObject.AddComponent<MinimapHud>();
                hud.mode = MinimapHud.Mode.City;
                hud.cityRadius = 320f;
                hud.textureSize = 512;
                hud.panelSize = 208f;
                hud.ringRadii = RingRadii;
                hud.radialCount = 8;
                hud.landmarks = new[]
                {
                    new Vector3(0f, 0f, 190f),    // castle hill
                    new Vector3(152f, 0f, -53f),  // cathedral
                    new Vector3(-142f, 0f, -65f), // adventurers' guild
                    new Vector3(0f, 0f, -300f),   // south gate
                    new Vector3(0f, 0f, -335f),   // harbour
                };
            }
        }

        // ================= Ground paving =================
        //
        // The review put it as "the ground is one flat colour, the houses look like cards pasted on a
        // board". The Blender parts already pave the whole city in one colour, but fixing that in
        // Blender means a 20 minute re-bake, so a textured ring road + radial avenues + central square
        // are laid here on the Unity side, at world scale, in one second - turning "flat colour board"
        // into a street surface with stone joints and scale.
        // The paving must press onto the Blender "solid ground": the first attempt at y=0.06 buried the
        // whole layer under the top face of ars_ground ("paving has no effect"). The second attempt
        // measured the ground height from the part bounding box and got 26.8 m, because ars_ground
        // includes the wall towers - that box top is not the walking surface (measured: a ray at the
        // origin hits y=0, and the house feet are also at 0), so the whole paving layer hung 27 m in
        // the air, higher than the tallest house in the city, and from below it was just a grey band at
        // the top of the frame.
        // It is now a constant, measured on the real ground, no longer guessed from a bounding box.

        // The Blender ground sits at y = 0; paving floats just above it so the imported
        // ars_ground mesh never z-fights with the street plates.
        private const float CityPavedY = 0.12f;

        private const float KerbTopY = CityPavedY + 0.17f;

        private void BuildSurfacePaving(Transform parent)
        {
            var verts = new List<Vector3>();
            var uvs = new List<Vector2>();
            var tris = new List<int>();
            float y = CityPavedY;
            const float tile = 2.6f;   // 2.6 m per tile: at 6 m the review measured a dV of only 1.8 between neighbouring stones, so the joints read as nothing

            // --- Ring road: one ribbon per entry of RingRadii ---
            for (int i = 0; i < RingRadii.Length; i++)
            {
                float r = RingRadii[i];
                float halfW = 3.6f;   // review: it used to be 10 m, two to three times wider than a house, so it read as a runway
                const int seg = 128;
                int start = verts.Count;
                for (int s = 0; s <= seg; s++)
                {
                    float a = (float)s / seg * Mathf.PI * 2f;
                    float ca = Mathf.Cos(a), sa = Mathf.Sin(a);
                    verts.Add(new Vector3(ca * (r - halfW), y, sa * (r - halfW)));
                    verts.Add(new Vector3(ca * (r + halfW), y, sa * (r + halfW)));
                    float u = a * r / tile;
                    uvs.Add(new Vector2(u, 0f));
                    uvs.Add(new Vector2(u, 2f * halfW / tile));
                }
                for (int s = 0; s < seg; s++)
                {
                    int v0 = start + s * 2, v1 = v0 + 1, v2 = v0 + 2, v3 = v0 + 3;
                    tris.Add(v0); tris.Add(v2); tris.Add(v1);
                    tris.Add(v1); tris.Add(v2); tris.Add(v3);
                }
            }

            // --- 8 radial avenues: from the square paving to the city wall ---
            const int radial = 8;
            const float halfWid = 4.2f;
            for (int k = 0; k < radial; k++)
            {
                float a = k * Mathf.PI * 2f / radial;
                var dir = new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a));
                var side = new Vector3(-dir.z, 0f, dir.x) * halfWid;
                const float r0 = 46f, r1 = 292f;
                const int steps = 12;
                int start = verts.Count;
                for (int s = 0; s <= steps; s++)
                {
                    float t = (float)s / steps;
                    Vector3 c = dir * Mathf.Lerp(r0, r1, t);
                    verts.Add(c - side + Vector3.up * y);
                    verts.Add(c + side + Vector3.up * y);
                    uvs.Add(new Vector2(t * (r1 - r0) / tile, 0f));
                    uvs.Add(new Vector2(t * (r1 - r0) / tile, 2f * halfWid / tile));
                }
                for (int s = 0; s < steps; s++)
                {
                    int v0 = start + s * 2, v1 = v0 + 1, v2 = v0 + 2, v3 = v0 + 3;
                    // The radial avenues need the opposite winding to the rings (here side is the
                    // tangential direction, not the radial one); copying the ring order leaves the whole
                    // avenue back-facing, i.e. invisible from above - the review measured exactly that:
                    // "6 ring roads have paving, 8 avenues have none".
                    tris.Add(v0); tris.Add(v1); tris.Add(v2);
                    tris.Add(v1); tris.Add(v3); tris.Add(v2);
                }
            }

            // --- Central square: a disc of radius 52 ---
            {
                const float R = 52f;
                const int seg = 64;
                int center = verts.Count;
                verts.Add(new Vector3(0f, y, 0f));
                uvs.Add(new Vector2(R / tile, R / tile));
                for (int s = 0; s <= seg; s++)
                {
                    float ang = (float)s / seg * Mathf.PI * 2f;
                    float ca = Mathf.Cos(ang), sa = Mathf.Sin(ang);
                    verts.Add(new Vector3(ca * R, y, sa * R));
                    uvs.Add(new Vector2((ca * R + R) / tile, (sa * R + R) / tile));
                }
                for (int s = 0; s < seg; s++)
                {
                    // The fan needs the reversed order as well, otherwise the square faces down and is
                    // invisible from above.
                    tris.Add(center);
                    tris.Add(center + 2 + s);
                    tris.Add(center + 1 + s);
                }
            }

            // The shared cobble material is now TriplanarLit: it samples by world position, so UV space
            // does not matter at all. No need to clone the material and retune tiling any more (the old
            // code multiplied it to a 26 cm tile and the mip chain turned the surface into grey mush).
            var pavingMat = MapMaterials.Get("cobble");
            CommitMesh("Paving", parent, verts, uvs, tris, pavingMat, false);
            BuildKerbs(parent);
        }

        /// <summary>
        /// Kerb stones: the review said the street "has no kerb and no gutter, not one line of scale".
        /// Each ring road gets a 0.3 m wide, 0.16 m high chamfered stone strip on both sides - a
        /// different normal is all the lighting needs to pick it out.
        /// </summary>
        private void BuildKerbs(Transform parent)
        {
            var verts = new List<Vector3>();
            var uvs = new List<Vector2>();
            var tris = new List<int>();
            float y0 = CityPavedY + 0.01f;
            float y1 = KerbTopY;

            for (int i = 0; i < RingRadii.Length; i++)
            {
                float r = RingRadii[i];
                for (int side = -1; side <= 1; side += 2)
                {
                    float rIn = r + side * 3.6f;
                    float rOut = r + side * 3.9f;
                    const int seg = 128;
                    int start = verts.Count;
                    for (int s = 0; s <= seg; s++)
                    {
                        float a = (float)s / seg * Mathf.PI * 2f;
                        float ca = Mathf.Cos(a), sa = Mathf.Sin(a);
                        verts.Add(new Vector3(ca * rIn, y0, sa * rIn));
                        verts.Add(new Vector3(ca * rOut, y1, sa * rOut));
                        float u = a * r / 3f;
                        uvs.Add(new Vector2(u, 0f));
                        uvs.Add(new Vector2(u, 0.2f));
                    }
                    for (int s = 0; s < seg; s++)
                    {
                        int v0 = start + s * 2, v1 = v0 + 1, v2 = v0 + 2, v3 = v0 + 3;
                        if (side < 0) { tris.Add(v0); tris.Add(v2); tris.Add(v1); tris.Add(v1); tris.Add(v2); tris.Add(v3); }
                        else { tris.Add(v0); tris.Add(v1); tris.Add(v2); tris.Add(v1); tris.Add(v3); tris.Add(v2); }
                    }
                }
            }
            // Review: "the kerb top and the road differ by only 4/255 in luminance - i.e. not at all".
            // It used to be marble (flat 0.90 luminance): the contrast was there, but a flat colour at eye
            // level is just a plastic sheet. stone_light has a squared-stone texture + normals; the albedo
            // is still clearly higher than the paving, and the 0.17 m height difference and the "this is a
            // different material" both hold at once.
            CommitMesh("Kerbs", parent, verts, uvs, tris, MapMaterials.Get("stone_light"), false);
        }

        private static void CommitMesh(string name, Transform parent,
            List<Vector3> verts, List<Vector2> uvs, List<int> tris, Material mat, bool shadows)
        {
            if (verts.Count == 0 || mat == null)
            {
                Debug.LogWarning("[AsuraCapital] mesh skipped: verts=" + verts.Count + " mat=" + (mat == null ? "null" : mat.name));
                return;
            }
            var m = new Mesh { name = name };
            m.SetVertices(verts);
            m.SetUVs(0, uvs);
            m.SetTriangles(tris, 0);
            m.RecalculateNormals();
            m.RecalculateBounds();

            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.AddComponent<MeshFilter>().sharedMesh = m;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = shadows
                ? UnityEngine.Rendering.ShadowCastingMode.On
                : UnityEngine.Rendering.ShadowCastingMode.Off;
        }

        // ================= Street frontage =================
        // The Blender ars_city part holds roughly 400 houses, spread over a 700 m diameter city district:
        // all that is left is "scattered boxes", which the bird's-eye shot reads as an empty ring - the
        // review called it "sprinkled bean curd". Here a real frontage is added along Blender's ring roads
        // (kit house_a..f); one prefab is one merged mesh, so 280 houses cost only 280 renderers, i.e. no
        // frame-rate concern.
        private static readonly float[] RingRadii = { 72f, 112f, 150f, 192f, 236f, 272f, 292f };

        private void DressStreets(Transform parent)
        {
            if (housePrefabs == null || housePrefabs.Length == 0)
            {
                Debug.LogWarning("[AsuraCapital] housePrefabs not wired; streets will stay empty");
                return;
            }

            var root = new GameObject("StreetFrontage").transform;
            root.SetParent(parent, false);

            // Landmarks and structures that must never be covered by street houses.
            var blocked = new[]
            {
                new Vector4(0f, 190f, 104f, 0f),      // castle platform
                new Vector4(0f, -9f, 48f, 0f),        // market square
                new Vector4(152f, -53f, 46f, 0f),     // cathedral
                new Vector4(-142f, -65f, 36f, 0f),    // guild hall
                new Vector4(0f, -300f, 46f, 0f),      // south gate
                new Vector4(0f, 300f, 46f, 0f),       // north gate
                new Vector4(0f, -335f, 64f, 0f),      // harbour
            };

            const float avenueClear = 13f;   // keep the main avenue clear of houses
            int budget = streetHouses;
            int placed = 0;
            var rng = new System.Random(20261023);

            for (int ri = 0; ri < RingRadii.Length && placed < budget; ri++)
            {
                float r = RingRadii[ri];
                // The further out the ring, the longer it is; use a wider spacing there so every ring ends
                // up with a similar density.
                float step = 9.5f + r * 0.012f;
                for (int side = -1; side <= 1 && placed < budget; side += 2)
                {
                    // Review: "the street is 2-3 times wider than the houses" - so pull both rows 3 m
                    // inwards, and only outside the 3.6 m kerb does the frontage start.
                    float rr = r + side * 7.4f;
                    int count = Mathf.Max(8, Mathf.RoundToInt(2f * Mathf.PI * rr / step));
                    for (int i = 0; i < count && placed < budget; i++)
                    {
                        float ang = (i + (side > 0 ? 0.45f : 0f)) / count * Mathf.PI * 2f;
                        float px = Mathf.Cos(ang) * rr;
                        float pz = Mathf.Sin(ang) * rr;

                        // Make way for the radial avenues: perpendicular distance to the nearest 45 degree
                        // sector midline.
                        float sector = Mathf.Repeat(ang, Mathf.PI / 4f);
                        float perp = Mathf.Abs(Mathf.Sin(sector)) * rr;
                        if (perp < avenueClear) continue;

                        bool hit = false;
                        for (int b = 0; b < blocked.Length; b++)
                        {
                            float dx = px - blocked[b].x;
                            float dz = pz - blocked[b].y;
                            if (dx * dx + dz * dz < blocked[b].z * blocked[b].z) { hit = true; break; }
                        }
                        if (hit) continue;

                        var prefab = housePrefabs[rng.Next(housePrefabs.Length)];
                        if (prefab == null) continue;

                        // Face the street: the prefab front is +Z, so point it at the ring centre.
                        var inward = new Vector3(-px, 0f, -pz).normalized;
                        var rot = Quaternion.LookRotation(inward) *
                                  Quaternion.Euler(0f, (float)(rng.NextDouble() * 6.0 - 3.0), 0f);

                        var go = Instantiate(prefab, new Vector3(px, 0f, pz), rot, root);
                        go.name = "House_" + placed;
                        float s = 1.05f + (float)rng.NextDouble() * 0.45f;
                        go.transform.localScale = new Vector3(s, s, s);
                        placed++;
                    }
                }
            }

            // A row against the wall: the outermost 20% of the radius used to be completely empty (36-42%
            // of the total area); add another row of houses along the inside of the wall, leaving a 4 m
            // service lane - now there is a skyline from outside the city as well.
            int wallRow = 0;
            for (float rr = 288f; rr >= 280f && placed < budget + 120; rr -= 7.5f)
            {
                float step = 7.6f;
                int count = Mathf.RoundToInt(2f * Mathf.PI * rr / step);
                for (int i = 0; i < count && placed < budget + 120; i++)
                {
                    float ang = (i + (wallRow % 2) * 0.5f) / count * Mathf.PI * 2f;
                    float px = Mathf.Cos(ang) * rr;
                    float pz = Mathf.Sin(ang) * rr;
                    // Keep the south gate (-Z) and the north gate passable.
                    if (Mathf.Abs(px) < 26f && Mathf.Abs(pz) > 250f) continue;
                    // The radial avenues need to stay clear here too (this was missed before, and the wall
                    // row blocked the 45 degree avenue outright).
                    float sectorW = Mathf.Repeat(ang, Mathf.PI / 4f);
                    if (Mathf.Abs(Mathf.Sin(sectorW)) * rr < 16f) continue;

                    var prefab = housePrefabs[rng.Next(housePrefabs.Length)];
                    if (prefab == null) continue;
                    var inward = new Vector3(-px, 0f, -pz).normalized;
                    var rot = Quaternion.LookRotation(inward) *
                              Quaternion.Euler(0f, (float)(rng.NextDouble() * 6.0 - 3.0), 0f);
                    var go = Instantiate(prefab, new Vector3(px, 0f, pz), rot, root);
                    go.name = "WallHouse_" + placed;
                    float s2 = 0.95f + (float)rng.NextDouble() * 0.3f;
                    go.transform.localScale = new Vector3(s2, s2, s2);
                    placed++;
                }
                wallRow++;
            }

            // Both sides of the avenue inside the south gate: the area between the wall and the first ring
            // used to be one big sheet of bare stone paving, and the player spawns right in the middle of
            // it - a measured frame was 91.6% the same stone floor, not even sky. Two rows of street-front
            // houses along the entrance avenue turn the gate mouth into a real street.
            int gateRow = 0;
            for (int side = -1; side <= 1; side += 2)
            {
                for (float z = -286f; z <= -70f; z += 8.6f)
                {
                    if (rng.NextDouble() < 0.12) continue;       // leave the odd gap
                    float x = side * (10.4f + (float)rng.NextDouble() * 3.2f);
                    // Keep the central axis between the south and north gates free (hauling, stalls and the
                    // camera all rely on it).
                    if (Mathf.Abs(x) < 9f) continue;
                    var prefab = housePrefabs[rng.Next(housePrefabs.Length)];
                    if (prefab == null) continue;
                    var face = new Vector3(-Mathf.Sign(x), 0f, 0f);   // front faces the avenue
                    var rot = Quaternion.LookRotation(face) *
                              Quaternion.Euler(0f, (float)(rng.NextDouble() * 4.0 - 2.0), 0f);
                    var go = Instantiate(prefab, new Vector3(x, 0f, z), rot, root);
                    go.name = "GateHouse_" + placed;
                    float sg = 1.0f + (float)rng.NextDouble() * 0.35f;
                    go.transform.localScale = new Vector3(sg, sg, sg);
                    placed++;
                    gateRow++;
                }
            }

            Debug.Log("[AsuraCapital] street houses placed = " + placed + " / " + budget +
                      ", gate houses = " + gateRow);
        }

        private void BuildAtmosphere(Transform world)
        {
            // The capital is 30 times the area of a town; the fog has to reach far, otherwise the castle
            // is invisible from the middle gate.
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogStartDistance = fogStart;
            RenderSettings.fogEndDistance = fogEnd;
            RenderSettings.fogColor = new Color(0.72f, 0.76f, 0.82f);

            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
            // Ambient light has to hold up the shadows, otherwise the 5 m alleys are just black blocks
            // (measured: 82% of the frame was dark pixels).
            RenderSettings.ambientSkyColor = new Color(0.66f, 0.69f, 0.76f);
            RenderSettings.ambientEquatorColor = new Color(0.56f, 0.53f, 0.47f);
            RenderSettings.ambientGroundColor = new Color(0.36f, 0.33f, 0.28f);

            // Skybox and shadow distance: without a skybox the top of the frame is a dead grey plate; with
            // the shadow distance too short you cannot see the wall shadow from the middle gate and the
            // whole city looks like a decal.
            KingdomAtmosphere.SetupSky();
            // A 200 m shadow distance with 4 cascades and a 4096 map gives ~0.2 m per texel, i.e. the
            // shadow at the foot of a wall is a hard cut with a "1 px to 150 level" step. Dropping to
            // 140 m halves the texel size and softens the shadow at the same time - the one knob in the
            // review list ("blocks with no contact") that really is a parameter fix.
            QualitySettings.shadowDistance = 140f;
            ApplySunShadows();

            // Same as the overworld: the camera skybox switch is reset to solid colour by
            // TopDownCameraRig.Start, so force it here.
            var rig = UnityEngine.Object.FindFirstObjectByType<TopDownCameraRig>();
            if (rig != null)
            {
                rig.UseSkybox = true;
                // The camera recomputes far from distance*2.5 (= 60) every frame, so only raising the
                // lower bound keeps the far plane.
                rig.minFarClip = 4500f;
            }

            // User: "do not limit the view distance". A capital at this scale should have no visible
            // clipping plane at all; the far plane is set to 4.5 km (the ground part is 1.3 km wide, and
            // from the north wall you can still see the hills beyond the south gate).
            var camera = Camera.main;
            if (camera != null)
            {
                camera.farClipPlane = 4500f;
                camera.nearClipPlane = 0.2f;
            }
            StartCoroutine(EnforceSkyboxFrames(6));
        }

        /// <summary>
        /// Sun shadow parameters. MapBootstrap only set Soft and the default bias 0.05/1.0 when it built
        /// the Sun; at this scale a 1 m normal bias is enough to push the whole contact shadow at the foot
        /// of a wall off the wall, so "houses look like they float above the ground". Here the normal bias
        /// is tightened to 0.3 (hugging the ground) and the depth bias to 0.04; strength drops from 0.92 to
        /// 0.62 so that stone joints and timber framing stay readable inside the shadow - the shadow of a
        /// woven-island roof is itself half transparent.
        /// The Sun may only be created by MapBootstrap after BuildAtmosphere, so EnforceSkyboxFrames calls
        /// this once more.
        /// </summary>
        private static void ApplySunShadows()
        {
            var lights = UnityEngine.Object.FindObjectsByType<Light>(UnityEngine.FindObjectsSortMode.None);
            for (int i = 0; i < lights.Length; i++)
            {
                var l = lights[i];
                if (l == null || l.type != LightType.Directional) continue;
                l.shadows = LightShadows.Soft;
                l.shadowStrength = 0.62f;
                l.shadowBias = 0.04f;
                l.shadowNormalBias = 0.3f;
                l.shadowNearPlane = 0.2f;
            }
        }

        private System.Collections.IEnumerator EnforceSkyboxFrames(int frames)
        {
            for (int i = 0; i < frames; i++)
            {
                if (i == 0) ApplySunShadows();
                var cam = Camera.main;
                if (cam != null && RenderSettings.skybox != null)
                {
                    cam.clearFlags = CameraClearFlags.Skybox;
                    cam.backgroundColor = new Color(0.72f, 0.78f, 0.86f);
                }
                // The far plane has to be pressed down again every frame here: BuildAtmosphere runs before
                // MapBootstrap creates the camera, so at that moment rig is still null and the Update
                // recomputes far from distance*2.5 = 60 m; the whole city is then clipped beyond 60 m
                // (measured: Camera.main.farClipPlane == 60).
                var rig = UnityEngine.Object.FindFirstObjectByType<TopDownCameraRig>();
                if (rig != null && rig.minFarClip < 4500f) rig.minFarClip = 4500f;
                if (cam != null && cam.farClipPlane < 4000f) cam.farClipPlane = 4500f;
                yield return null;
            }
        }

        private void BuildGatePortal(Transform world)
        {
            var root = new GameObject("BackToKingdom").transform;
            root.SetParent(world, false);
            // Walk back out of the gate onto the kingdom road at z=-312.
            ScenePortal.Create(root, new Vector3(0f, 0f, -312f),
                MapId.AsuraKingdom, "start", "Back to the Kingdom Road", 0f);
        }

        private void BuildPeople(Transform parent)
        {
            // Two guards flanking the gate, plus townsfolk, all standing on the Blender ground at z=-300.
            SpawnNpc(NpcRole.Guard, "Gate Guard", new Vector3(-7f, 0f, -276f), 0f,
                new[] { "Hold there, traveller. The capital is open to you.",
                        "Keep to the main avenue and you will not get lost." });
            SpawnNpc(NpcRole.Guard, "Gate Guard", new Vector3(7f, 0f, -276f), 180f,
                new[] { "Welcome to the Asura capital.",
                        "The market square is straight up the avenue." });
            SpawnNpc(NpcRole.Villager, "Traveller", new Vector3(0f, 0f, -250f), 200f,
                new[] { "They say the king rebuilt the whole city in one year.",
                        "The cathedral bells carry all the way across the river." });

            // Eight wandering townsfolk spread around the lower city.
            var rng = new System.Random(20261024);
            string[] names = { "Aldric", "Bran", "Cedric", "Dara", "Edric", "Fen",
                               "Garin", "Hilda", "Ivor", "Jorun", "Kael", "Lira" };
            for (int k = 0; k < 8; k++)
            {
                float ang = k * Mathf.PI * 2f / 8f;
                var dir = new Vector3(Mathf.Cos(ang), 0f, Mathf.Sin(ang));
                var side = new Vector3(-dir.z, 0f, dir.x);
                for (int i = 0; i < 2; i++)
                {
                    float r = 62f + i * 46f + (float)rng.NextDouble() * 18f;
                    float lat = (rng.NextDouble() < 0.5 ? -1f : 1f) * (5.6f + (float)rng.NextDouble() * 1.6f);
                    var p = dir * r + side * lat;
                    SpawnNpc(NpcRole.Villager, names[rng.Next(names.Length)],
                        new Vector3(p.x, 0f, p.z), (float)rng.NextDouble() * 360f);
                }
            }
        }

        /// <summary>
        /// Street decoration: benches, crates, hand carts, stalls, wells, fences. Only on the outside of the
        /// kerb and the edge of the square - never on the roadway; the previous review found no props at
        /// all on the street.
        /// </summary>
        private void BuildProps(Transform parent)
        {
            if (propPrefabs == null || propPrefabs.Length == 0 || propCount <= 0)
            {
                Debug.LogWarning("[AsuraCapital] propPrefabs not wired; street props will stay empty");
                return;
            }
            var rng = new System.Random(20261025);
            int placed = 0;
            var root = new GameObject("StreetProps").transform;
            root.SetParent(parent, false);

            // Line the 8 radial avenues, 5.4-7.2 m outside the kerb.
            for (int k = 0; k < 8 && placed < propCount; k++)
            {
                float ang = k * Mathf.PI * 2f / 8f;
                var dir = new Vector3(Mathf.Cos(ang), 0f, Mathf.Sin(ang));
                var side = new Vector3(-dir.z, 0f, dir.x);
                for (float r = 58f; r < 286f && placed < propCount; r += 13f + (float)rng.NextDouble() * 7f)
                {
                    float lat = (rng.NextDouble() < 0.5 ? -1f : 1f) * (5.4f + (float)rng.NextDouble() * 1.8f);
                    var p = dir * r + side * lat;
                    var prefab = propPrefabs[rng.Next(propPrefabs.Length)];
                    if (prefab == null) continue;
                    var go = Instantiate(prefab, new Vector3(p.x, 0f, p.z),
                        Quaternion.Euler(0f, (float)rng.NextDouble() * 360f, 0f), root);
                    go.name = "Prop_" + placed;
                    placed++;
                }
            }

            // A ring of stalls and benches around the edge of the square.
            for (int i = 0; i < 40 && placed < propCount + 40; i++)
            {
                float a = (float)rng.NextDouble() * Mathf.PI * 2f;
                float rad = 34f + (float)rng.NextDouble() * 16f;
                var prefab = propPrefabs[rng.Next(propPrefabs.Length)];
                if (prefab == null) continue;
                var go = Instantiate(prefab, new Vector3(Mathf.Cos(a) * rad, 0f, Mathf.Sin(a) * rad),
                    Quaternion.Euler(0f, (float)rng.NextDouble() * 360f, 0f), root);
                go.name = "Prop_Sq_" + placed;
                placed++;
            }

            Debug.Log("[AsuraCapital] street props placed = " + placed + " / " + propCount);
        }

        protected override Vector3 ResolveSpawn(string spawnId)
        {
            return SouthGateSpawn;
        }
    }
}
