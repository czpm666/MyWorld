using System.Collections.Generic;
using UnityEngine;
using MyWorld.Kingdom;

namespace MyWorld.Maps
{
    /// <summary>
    /// Asura Kingdom overworld: a 3km x 3km plain with the capital "Ars" at the center
    /// and dozens of small towns on three rings around it.
    ///
    /// Design notes:
    ///   * Towns are whole Blender FBX prefabs (~150k tris each); 30 of them is already
    ///     near the render budget, so there is no distance LOD - fog does that job.
    ///   * The overworld only sells "scale": ground, road network, fog, mountains.
    ///     Detail lives inside the towns and inside the capital scene.
    ///   * Ring radii 420 / 760 / 1120 m, counts 9 / 11 / 12, deterministic seed, so the
    ///     same town is always in the same place.
    /// </summary>
    public class KingdomWorldMap : MapBootstrap
    {
        [Header("Kingdom overworld")]
        [Tooltip("Town prefabs (farm_* / mine_* / port_*), filled by the kingdom menu.")]
        public GameObject[] townPrefabs;

        [Tooltip("Max number of towns; the rings may hold fewer after spacing checks.")]
        public int townCount = 30;

        [Tooltip("Map edge in meters. Fog plus the mountain ring hide the border.")]
        public float worldSize = 3000f;

        [Tooltip("Minimum distance between two towns (a town is about 120m across).")]
        public float minTownGap = 250f;

        [Tooltip("Tree/bush prefabs used for roadside planting and groves (optional).")]
        public GameObject[] treePrefabs;

        [Tooltip("House prefabs (house_a..house_f) used for the capital's roof mass.")]
        public GameObject[] housePrefabs;

        [Tooltip("How many roadside/grove trees to plant. 0 disables planting.")]
        public int treeCount = 900;

        private const int LayoutSeed = 20261022;

        // ring radius, town count. The capital wall stands at r=298 and a town is ~120 m
        // across, so the innermost ring has to clear 298 + 60 + gap.
        private static readonly Vector2Int[] Rings =
        {
            new Vector2Int(560, 10),
            new Vector2Int(880, 11),
            new Vector2Int(1200, 12),
        };

        // Outside the south gate, on the approach road, facing the city.
        // Must stand well back: at -352 the gate is only 56 m away, so the third-person
        // camera (16 m behind) fills half the frame with the 22 m wall and the dark
        // gate tunnel (measured 51.7% of pixels below luminance 80).
        private static readonly Vector3 CapitalSpawn = new Vector3(16f, 0.2f, -470f);

        protected override void BuildEnvironment(Transform world)
        {
            var root = new GameObject("Ground").transform;
            root.SetParent(world, false);

            // Town spots are needed BEFORE the ground mesh, because the ground is
            // flattened under each town (otherwise a town half-floats on a slope).
            s_spots = ComputeSpots();

            // Ground = one big mesh with gentle relief; beyond 1.15km it rises into a
            // mountain ring so the horizon is closed by terrain, not by a straight edge.
            // UV: one grass tile every 4m. MapMaterials bakes tiling=24 into the
            // material, so UV units must be px/96 (96m/24 = 4m per tile). The old
            // px/6 mapping gave a 0.25m tile that mip-averaged into flat green.
            var mesh = BuildGroundMesh(worldSize + 600f, 120);
            var go = new GameObject("GroundMesh");
            go.transform.SetParent(root, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            // The terrain uses the _VERTEXCOLOR variant: around a town the grass is tinted
            // towards trampled earth, so the town plate does not read as a sheet of paper
            // lying on flat green (the plate edge showed a hard colour ring before).
            var grassMat = MapMaterials.Get("grass");
            grassMat = grassMat != null ? new Material(grassMat) : null;
            if (grassMat != null) grassMat.EnableKeyword("_VERTEXCOLOR");
            mr.sharedMaterial = grassMat;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            var mc = go.AddComponent<MeshCollider>();
            mc.sharedMesh = mesh;
        }

        // Town spots: three rings, deterministic seed. Height = ground height at center.
        private List<Vector3> ComputeSpots()
        {
            var rng = new System.Random(LayoutSeed);
            var spots = new List<Vector3>();
            float halfAvailable = worldSize * 0.5f - 220f;

            for (int ri = 0; ri < Rings.Length; ri++)
            {
                int radius = Rings[ri].x;
                int count = Rings[ri].y;
                float phase = (float)rng.NextDouble();
                for (int i = 0; i < count; i++)
                {
                    if (spots.Count >= townCount) break;
                    float a = (i + phase) / count * Mathf.PI * 2f;
                    float jitterR = ((float)rng.NextDouble() - 0.5f) * 90f;
                    float rr = radius + jitterR;
                    var p = new Vector3(Mathf.Cos(a) * rr, 0f, Mathf.Sin(a) * rr);
                    if (Mathf.Abs(p.x) > halfAvailable || Mathf.Abs(p.z) > halfAvailable) continue;
                    if (!IsFarEnough(spots, p, minTownGap)) continue;
                    p.y = RawHeight(p.x, p.z);
                    spots.Add(p);
                }
            }
            return spots;
        }

        // ---------------- terrain ----------------

        private static List<Vector3> s_spots = new List<Vector3>();

        private static float RawHeight(float x, float z)
        {
            float h = Mathf.PerlinNoise(x * 0.0011f + 11.3f, z * 0.0011f + 7.1f) * 26.0f
                    + Mathf.PerlinNoise(x * 0.0042f + 3.7f, z * 0.0042f + 1.9f) * 8.0f
                    + Mathf.PerlinNoise(x * 0.021f, z * 0.021f) * 1.1f;
            // Near-field relief: the 0.0011 wave is ~900 m long, so inside a 320 m view it is
            // almost a straight line (the review measured a 4-step luminance spread over 29x29
            // windows, i.e. no terrain at all). Two mid-frequency octaves make 100-300 m read
            // as slope and shading; amplitude is kept under 3 m so town plates and the road
            // surface never crack.
            h += Mathf.PerlinNoise(x * 0.0063f + 29.1f, z * 0.0063f + 14.7f) * 3.4f;
            h += Mathf.PerlinNoise(x * 0.019f + 53.3f, z * 0.019f + 31.9f) * 0.9f;
            h -= 17.0f;

            float r = Mathf.Sqrt(x * x + z * z);

            // Mountain ring. A single smooth Perlin hill read as a fog wall, so this is
            // RIDGED noise (1-|2n-1|, which is peaky) at three scales: broad massifs,
            // secondary spurs, then a fine crest jitter. Height ramps in from 1050 m.
            float ramp = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(1050f, 1750f, r));
            float m1 = Ridged(x, z, 0.0014f, 41f);
            float m2 = Ridged(x, z, 0.0038f, 97f);
            float m3 = Ridged(x, z, 0.0093f, 17f);
            float ridge = 34f + 150f * m1 * m1 + 52f * m2 + 20f * m3;
            h = Mathf.Lerp(h, Mathf.Max(h, ridge), ramp);

            // Flatten the whole capital footprint: the wall stands at r=298, so a ramp
            // starting at 90 m left the wall base and the gate on a slope.
            h *= Mathf.InverseLerp(360f, 500f, r);
            return h;
        }

        /// <summary>Ridged noise (1-|2n-1|): peaky, unlike raw Perlin which gives one smooth dome.</summary>
        private static float Ridged(float x, float z, float freq, float off)
        {
            float n = Mathf.PerlinNoise(x * freq + off, z * freq + off * 0.73f);
            return 1f - Mathf.Abs(n * 2f - 1f);
        }

        /// <summary>Ground height: flattened near town centers, noise elsewhere.</summary>
        public static float GroundHeight(float x, float z)
        {
            float h = RawHeight(x, z);
            if (s_spots == null) return h;
            var p = new Vector2(x, z);
            for (int i = 0; i < s_spots.Count; i++)
            {
                Vector3 s = s_spots[i];
                float d = Vector2.Distance(p, new Vector2(s.x, s.z));
                if (d >= 92f) continue;
                // A town is a plate of +/-45 m (63.6 m to the corners); flattening only out to
                // 44 m left a 3-5 m step at the corners, so the plate hung in the air or the
                // terrain poked through it. Push fully flat inside 66 m (past the corners), then
                // blend back into the noise terrain by 92 m.
                float t = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(66f, 92f, d));
                h = Mathf.Lerp(s.y, h, t);

                // The town plate top face is exactly s.y; a dark road strip painted on it used to
                // flicker and read like tape. Sink the ground 8 cm under the plate so the last 2 m
                // of grass edge hides the seam in shadow.
                float sink = 0.08f * (1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(58f, 70f, d)));
                h -= sink;
            }
            return h;
        }

        /// <summary>Horizontal distance to the nearest town (m); a huge value when there are none.</summary>
        private static float NearestTownDistance(float x, float z)
        {
            if (s_spots == null || s_spots.Count == 0) return 1e6f;
            float best = 1e6f;
            for (int i = 0; i < s_spots.Count; i++)
            {
                float dx = x - s_spots[i].x, dz = z - s_spots[i].z;
                float d = dx * dx + dz * dz;
                if (d < best) best = d;
            }
            return Mathf.Sqrt(best);
        }

        private static Mesh BuildGroundMesh(float size, int seg)
        {
            int n = seg + 1;
            var verts = new Vector3[n * n];
            var uvs = new Vector2[n * n];
            var colors = new Color[n * n];
            var tris = new int[seg * seg * 6];
            float half = size * 0.5f;
            float step = size / seg;
            int vi = 0;
            for (int z = 0; z < n; z++)
            {
                for (int x = 0; x < n; x++)
                {
                    float px = -half + x * step;
                    float pz = -half + z * step;
                    verts[vi] = new Vector3(px, GroundHeight(px, pz), pz);
                    uvs[vi] = new Vector2(px / 96f, pz / 96f);

                    // Vertex colour: within 46 m of a town the ground is trampled earth, past 96 m it
                    // is the base meadow. Noise jitter breaks the circular edge so it reads as ground
                    // worn by feet rather than a drawn ring.
                    float d = NearestTownDistance(px, pz);
                    float jitter = (Mathf.PerlinNoise(px * 0.031f + 11.3f, pz * 0.031f + 7.9f) - 0.5f) * 26f;
                    // The town plate is +/-45 m (63.6 m to the corners), so the tint has to start outside
                    // the plate and only finish at 130 m; otherwise the only thing tinted is the ground
                    // under the plate, i.e. nothing visible.
                    float t = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(52f, 132f, d + jitter));
                    // Keep it a light "trampled" tint and break it with a second noise layer, otherwise
                    // the whole meadow becomes one big orange disc.
                    float patch = 0.45f + 0.55f * Mathf.PerlinNoise(px * 0.115f + 3.1f, pz * 0.115f + 9.7f);
                    Color worn = new Color(0.92f, 0.89f, 0.78f);
                    Color c = Color.Lerp(Color.white, worn, (1f - t) * 0.85f * patch);

                    // The meadow around a town used to be one uniform mass of green - in the aerial
                    // shot it read as a sheet of green felt. Two large-scale patches (dry yellow, wet
                    // dark) with only a 12% brightness swing are enough to break it up.
                    float patchA = Mathf.PerlinNoise(px * 0.0061f + 41.7f, pz * 0.0061f + 13.9f);
                    float patchB = Mathf.PerlinNoise(px * 0.026f + 5.3f, pz * 0.026f + 77.1f);
                    Color dry = new Color(1.22f, 1.10f, 0.74f);
                    Color lush = new Color(0.82f, 0.96f, 0.82f);
                    Color meadow = Color.Lerp(lush, dry, Mathf.Clamp01(patchA * 1.15f));
                    meadow *= 0.94f + 0.12f * patchB;
                    c = new Color(c.r * meadow.r, c.g * meadow.g, c.b * meadow.b);

                    // Slopes stop being grass: above 40 degrees turn to dry earth / rock. The old
                    // mountain ring was one continuous green face, which read as a green wall (very
                    // obvious behind the stone gate).
                    float hx = GroundHeight(px + 3f, pz);
                    float hz = GroundHeight(px, pz + 3f);
                    float slope = Mathf.Sqrt((hx - verts[vi].y) * (hx - verts[vi].y) + (hz - verts[vi].y) * (hz - verts[vi].y)) / 3f;
                    float rockAmt = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.55f, 1.05f, slope));
                    Color rock = new Color(0.78f, 0.72f, 0.60f);
                    c = Color.Lerp(c, rock, rockAmt * 0.85f);

                    colors[vi] = c;
                    vi++;
                }
            }
            int ti = 0;
            for (int z = 0; z < seg; z++)
            {
                for (int x = 0; x < seg; x++)
                {
                    int i0 = z * n + x;
                    tris[ti++] = i0;
                    tris[ti++] = i0 + n;
                    tris[ti++] = i0 + 1;
                    tris[ti++] = i0 + 1;
                    tris[ti++] = i0 + n;
                    tris[ti++] = i0 + n + 1;
                }
            }
            var m = new Mesh { name = "KingdomGround" };
            m.vertices = verts;
            m.uv = uvs;
            m.colors = colors;
            m.triangles = tris;
            m.RecalculateNormals();
            m.RecalculateBounds();
            return m;
        }

        private static Material s_lawn;

        /// <summary>
        /// Swap the grass patches on a town's ground plate to the same grass material as the
        /// overworld terrain. The prefab's M_pasture is a flat albedo (0.32/0.42/0.19) while the
        /// terrain meadow uses the kit_grass texture, so every town sat on a pale green square
        /// that read as a decal. After the swap plate and terrain match colour and the border is
        /// essentially invisible.
        /// </summary>
        private static void MatchTownLawn(GameObject town)
        {
            if (s_lawn == null) s_lawn = MapMaterials.Get("grass");
            if (s_lawn == null) return;
            foreach (var r in town.GetComponentsInChildren<MeshRenderer>(true))
            {
                var mats = r.sharedMaterials;
                bool changed = false;
                for (int i = 0; i < mats.Length; i++)
                {
                    var m = mats[i];
                    if (m == null) continue;
                    string n = m.name.ToLowerInvariant();
                    if (n.StartsWith("m_pasture") || n.StartsWith("m_lawn") || n.StartsWith("m_grass"))
                    {
                        mats[i] = s_lawn;
                        changed = true;
                    }
                }
                if (changed) r.sharedMaterials = mats;
            }
        }

        protected override void BuildMapContent(Transform world)
        {
            var rng = new System.Random(LayoutSeed);
            var spots = s_spots != null && s_spots.Count > 0 ? s_spots : ComputeSpots();

            var townRoot = new GameObject("Towns").transform;
            townRoot.SetParent(world, false);

            var roads = new List<Vector3[]>();

            // Terrain decides a town's "character": low ground is a water town, high ground is a
            // stone town, everything in between is a farm town. These used to rotate purely by
            // (index + rng) % 9, which put a harbour with its own sea surface on a 37 m hill
            // (measured: port_a_29 at pos.y = 37.4, the sea reading as a floating blue plate).
            string[] kinds = AssignKinds(spots);
            // Half width of each road. Everything used to be 10 m, twice a town's 5 m main
            // street: thirty ten-metre mud ribbons on screen at once read as a field of mud.
            // Back roads are 5.2 m (the town main-street width); only the capital approach
            // keeps 11 m for the ceremonial look.
            var roadHalfW = new List<float>();
            int placed = 0;
            for (int i = 0; i < spots.Count; i++)
            {
                GameObject prefab = PickPrefab(townPrefabs, rng, i, kinds[i]);
                if (prefab == null) continue;
                var pos = new Vector3(spots[i].x, spots[i].y, spots[i].z);
                // A town gate faces the capital. In Blender the village mouth opens on the -Y side,
                // which after import is the prefab's local -Z (measured FBX mapping: Unity X =
                // -Blender X, Unity Z = +Blender Y). So "local -Z points at the capital" solves to
                // yaw = atan2(pos.x, pos.z). It used to be pure random: with the 30 towns facing
                // all directions the world roads rammed into their side walls - a large part of the
                // "the layout is a mess" verdict.
                float yaw = Mathf.Atan2(pos.x, pos.z) * Mathf.Rad2Deg;
                var go = Instantiate(prefab, pos, Quaternion.Euler(0f, yaw, 0f), townRoot);
                go.name = prefab.name + "_" + i;
                placed++;
                MatchTownLawn(go);

                // One road per town to the capital: this is what makes it a kingdom
                // instead of a scatter of islands. The town end stops at the gate
                // apron (36 m out, right at the plate edge) and the capital end stops
                // at the ring road (r=380) rather than at the origin - 30 ribbons
                // meeting at one point looked like a spider, not a road network.
                Vector3 toCapital = new Vector3(-pos.x, 0f, -pos.z);
                float dist = toCapital.magnitude;
                Vector3 townEnd = TargetGate(spots, i);
                if (dist < 70f) townEnd = new Vector3(pos.x, 0f, pos.z);
                Vector3 ringEnd = toCapital.normalized * 380f;
                roads.Add(new[] { townEnd, ringEnd });
                roadHalfW.Add(2.6f);

                // Side roads: one per town would be pure "spokes on a wheel", which reads as a rim
                // in an aerial shot. Give about two thirds of the towns a road that leaves from the
                // town gate towards the nearest other town, so the network has junctions and forks
                // instead of a grid.
                if (i % 3 != 2 && spots.Count > 2)
                {
                    int j = NearestOtherTown(spots, i);
                    if (j >= 0)
                    {
                        Vector3 mid = Vector3.Lerp(townEnd, ringEnd, 0.45f);
                        // The side road also ends at the target town's gate instead of some arbitrary
                        // spot 60 m from its centre; the old version kept ramming into the back of
                        // houses from the side.
                        Vector3 gateEnd = TargetGate(spots, j);
                        if ((gateEnd - mid).magnitude > 120f)
                        {
                            roads.Add(new[] { mid, gateEnd });
                            roadHalfW.Add(2.2f);
                        }
                    }
                }
            }

            // Approach road: spawn point to the gate, and the player must open their eyes
            // on a road. Runs from outside the wall to just short of the gate arch.
            // The capital approach: the only road still 11 m wide.
            roads.Add(new[] { new Vector3(0f, 0f, -520f), new Vector3(0f, 0f, -300f) });
            roadHalfW.Add(5.5f);

            // The 30 town roads all used to stop at radius 312, i.e. all 30 13 m-wide dirt ribbons
            // were packed into one ring. Standing outside the south gate and looking in, the whole
            // frame (measured flat RGB 106,82,42) was a mud field. One ring road now collects all
            // 30 roads: the mud becomes a readable "ring + spokes" network and outside the ring it
            // is still meadow.
            const float ringR = 380f;
            const int ringSeg = 56;
            for (int k = 0; k < ringSeg; k++)
            {
                float a0 = (float)k / ringSeg * Mathf.PI * 2f;
                float a1 = (float)(k + 1) / ringSeg * Mathf.PI * 2f;
                roads.Add(new[]
                {
                    new Vector3(Mathf.Cos(a0) * ringR, 0f, Mathf.Sin(a0) * ringR),
                    new Vector3(Mathf.Cos(a1) * ringR, 0f, Mathf.Sin(a1) * ringR),
                });
                roadHalfW.Add(3.0f);
            }

            BuildRoadMesh(world, roads, roadHalfW);
            BuildCapitalGate(world);
            BuildCityRing(world, rng);
            BuildTrees(world, roads, rng);

            Debug.Log("[KingdomWorld] towns=" + placed + " spots=" + spots.Count +
                      " roads=" + roads.Count + " size=" + worldSize + "m");
        }

        /// <summary>
        /// Assign the 30 town types by terrain height: the lowest batch becomes water towns (the
        /// harbour prefab carries its own sea plane, so on high ground it is a floating sea), the
        /// highest batch becomes stone towns, the rest farm towns.
        /// </summary>
        private static string[] AssignKinds(List<Vector3> spots)
        {
            int n = spots.Count;
            var kinds = new string[n];
            var order = new int[n];
            for (int i = 0; i < n; i++) { kinds[i] = "farm"; order[i] = i; }
            System.Array.Sort(order, (a, b) => spots[a].y.CompareTo(spots[b].y));

            // Water towns: only low ground below 3 m gets a harbour, at most 11 of them.
            int ports = 0;
            for (int k = 0; k < n && ports < 11; k++)
            {
                int i = order[k];
                if (spots[i].y > 3f) break;
                kinds[i] = "port";
                ports++;
            }

            // Stone towns: the highest 5 of the remaining spots, and only above 6 m - mining on flat
            // ground makes no sense.
            int mines = 0;
            for (int k = n - 1; k >= 0 && mines < 5; k--)
            {
                int i = order[k];
                if (kinds[i] != "farm") continue;
                if (spots[i].y < 6f) break;
                kinds[i] = "mine";
                mines++;
            }
            return kinds;
        }

        /// <summary>Distance from a town gate to the town centre: lands exactly on the edge of the prefab ground plate, so the world road joins the small plaza in front of the gate.</summary>
        private const float GateDist = 36f;

        /// <summary>World position of a town gate (its entrance).</summary>
        /// <remarks>
        /// <remarks>
        /// Blender convention: the village mouth opens on the -Y side and the main street runs
        /// through on the Y axis. After FBX import Unity local X = -Blender X and Unity local Z =
        /// +Blender Y (verified against farm_a's barn_a / barn_b / windmill vertices), so the
        /// village mouth is the prefab's local -Z. Placing with yaw = atan2(pos.x, pos.z) points
        /// that -Z straight at the capital, so the gate lands "36 m from the town centre towards
        /// the capital" and the world road joins the plaza in front of the gate instead of hitting
        /// a side wall.
        /// </remarks>
        private static Vector3 TargetGate(List<Vector3> spots, int i)
        {
            Vector3 p = spots[i];
            Vector3 toCapital = new Vector3(-p.x, 0f, -p.z);
            if (toCapital.sqrMagnitude < 1f) return new Vector3(p.x, 0f, p.z);
            return new Vector3(p.x, 0f, p.z) + toCapital.normalized * GateDist;
        }

        private static int NearestOtherTown(List<Vector3> spots, int from)
        {
            int best = -1;
            float bestD = float.MaxValue;
            for (int k = 0; k < spots.Count; k++)
            {
                if (k == from) continue;
                float d = (spots[k] - spots[from]).sqrMagnitude;
                if (d < bestD) { bestD = d; best = k; }
            }
            return best;
        }

        private static bool IsFarEnough(List<Vector3> spots, Vector3 p, float gap)
        {
            float g2 = gap * gap;
            for (int i = 0; i < spots.Count; i++)
            {
                if ((spots[i] - p).sqrMagnitude < g2) return false;
            }
            return true;
        }

        private static GameObject PickPrefab(GameObject[] prefabs, System.Random rng, int index)
        {
            if (prefabs == null || prefabs.Length == 0) return null;
            // Rotate with a jitter so all three archetypes show up and no run is all-farm
            int biased = (index + rng.Next(0, prefabs.Length)) % prefabs.Length;
            return prefabs[biased];
        }

        /// <summary>Pick a variant by type (farm / port / mine, matched against the prefab name prefix); falls back to the plain rotation when no such type is wired.</summary>
        private static GameObject PickPrefab(GameObject[] prefabs, System.Random rng, int index, string kind)
        {
            if (prefabs == null || prefabs.Length == 0) return null;
            if (string.IsNullOrEmpty(kind)) return PickPrefab(prefabs, rng, index);

            var pool = new List<GameObject>();
            for (int i = 0; i < prefabs.Length; i++)
                if (prefabs[i] != null && prefabs[i].name.StartsWith(kind, System.StringComparison.OrdinalIgnoreCase))
                    pool.Add(prefabs[i]);
            if (pool.Count == 0) return PickPrefab(prefabs, rng, index);

            int pick = (index + rng.Next(0, pool.Count)) % pool.Count;
            return pool[pick];
        }

        private void BuildRoadMesh(Transform world, List<Vector3[]> roads, List<float> halfWidths)
        {
            if (roads.Count == 0) return;
            const float stepLen = 5f;
            const float lift = 0.22f;
            var verts = new List<Vector3>();
            var uvs = new List<Vector2>();
            var tris = new List<int>();

            for (int i = 0; i < roads.Count; i++)
            {
                Vector3 a = roads[i][0];
                Vector3 b = roads[i][1];
                float halfW = (halfWidths != null && i < halfWidths.Count) ? halfWidths[i] : 2.6f;
                var flat = new Vector3(b.x - a.x, 0f, b.z - a.z);
                float len = flat.magnitude;
                if (len < 1f) continue;
                Vector3 dir = flat / len;

                // Roads should bend. Every road used to be a straight two-point line, which the
                // review called "drawn with a ruler: 30 spokes straight into the capital". Use a
                // sine bulge that is 0 at both ends (so the road still meets the town gate and the
                // city gate) and then add a second, smaller wobble on top.
                float amp = Mathf.Min(len * 0.055f, 46f);
                float phase = (float)((i * 12.9898 + 4.1) % 6.2831853);
                float phase2 = (float)((i * 7.233 + 1.7) % 6.2831853);

                int steps = Mathf.Max(2, Mathf.CeilToInt(len / stepLen));
                var centres = new Vector3[steps + 1];
                for (int s = 0; s <= steps; s++)
                {
                    float t = (float)s / steps;
                    float env = Mathf.Sin(t * Mathf.PI);                 // 0 at both ends
                    float lateral = amp * Mathf.Sin(t * Mathf.PI + phase) * env
                                  + 5.5f * Mathf.Sin(t * Mathf.PI * 3f + phase2) * env;
                    Vector3 c = Vector3.Lerp(a, b, t);
                    c.x += -dir.z * lateral;
                    c.z += dir.x * lateral;
                    centres[s] = c;
                }

                int start = verts.Count;
                for (int s = 0; s <= steps; s++)
                {
                    float t = (float)s / steps;
                    Vector3 c = centres[s];
                    Vector3 tangent = (s == 0) ? (centres[1] - c)
                                    : (s == steps) ? (c - centres[steps - 1])
                                    : (centres[s + 1] - centres[s - 1]);
                    tangent.y = 0f;
                    if (tangent.sqrMagnitude < 0.0001f) tangent = dir;
                    tangent.Normalize();
                    Vector3 side = new Vector3(-tangent.z, 0f, tangent.x) * halfW;
                    Vector3 l = c - side;
                    Vector3 r = c + side;
                    // Follow the terrain: the old flat strip sank under any slope, and
                    // 14 m steps could not follow a 1-in-8 hillside at all.
                    l.y = GroundHeight(l.x, l.z) + lift;
                    r.y = GroundHeight(r.x, r.z) + lift;
                    verts.Add(l);
                    verts.Add(r);
                    uvs.Add(new Vector2(0f, t * len / 6f));
                    uvs.Add(new Vector2(1f, t * len / 6f));
                }
                for (int s = 0; s < steps; s++)
                {
                    int v0 = start + s * 2;   // east edge at s
                    int v1 = v0 + 1;          // west edge at s
                    // Winding matched to the ground mesh (see BuildGroundMesh): the
                    // mirrored order used here before made every road back-facing, so
                    // roads were invisible from above and only visible from below.
                    tris.Add(v1); tris.Add(v1 + 2); tris.Add(v0);
                    tris.Add(v0); tris.Add(v1 + 2); tris.Add(v0 + 2);
                }
            }
            if (verts.Count == 0) return;

            var m = new Mesh { name = "KingdomRoads" };
            m.SetVertices(verts);
            m.SetUVs(0, uvs);
            m.SetTriangles(tris, 0);
            m.RecalculateNormals();
            m.RecalculateBounds();

            var go = new GameObject("Roads");
            go.transform.SetParent(world, false);
            go.AddComponent<MeshFilter>().sharedMesh = m;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = MapMaterials.Get("road") ?? MapMaterials.Get("dirt");
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        }

        private void BuildTrees(Transform world, List<Vector3[]> roads, System.Random rng)
        {
            if (treePrefabs == null || treePrefabs.Length == 0 || treeCount <= 0) return;

            var root = new GameObject("Trees").transform;
            root.SetParent(world, false);
            int placed = 0;

            // 1) Roadside rows. A road through empty grass has no scale reference at all;
            //    evenly spaced trees are what makes distance readable.
            for (int i = 0; i < roads.Count && placed < treeCount; i++)
            {
                Vector3 a = roads[i][0];
                Vector3 b = roads[i][1];
                var flat = new Vector3(b.x - a.x, 0f, b.z - a.z);
                float len = flat.magnitude;
                if (len < 40f) continue;
                Vector3 dir = flat / len;
                Vector3 side = new Vector3(-dir.z, 0f, dir.x);
                for (float t = 20f; t < len - 20f && placed < treeCount; t += 18f)
                {
                    if (rng.NextDouble() < 0.45) continue;
                    for (int s = -1; s <= 1; s += 2)
                    {
                        if (rng.NextDouble() < 0.25) continue;
                        float off = 13f + (float)rng.NextDouble() * 13f;
                        Vector3 p = a + dir * t + side * (off * s);
                        // The last stretch of every road runs inside the capital wall.
                        if (p.sqrMagnitude < 330f * 330f) continue;
                        PlaceTree(root, p, rng);
                        placed++;
                        if (placed >= treeCount) break;
                    }
                }
            }

            // 2) Groves. Noise mask keeps them clustered instead of a uniform sprinkle.
            int guard = 0;
            while (placed < treeCount && guard < treeCount * 20)
            {
                guard++;
                float ang = (float)rng.NextDouble() * Mathf.PI * 2f;
                float rr = 345f + (float)rng.NextDouble() * 1100f;
                float px = Mathf.Cos(ang) * rr;
                float pz = Mathf.Sin(ang) * rr;
                if (Mathf.PerlinNoise(px * 0.004f + 5.4f, pz * 0.004f + 2.7f) < 0.53f) continue;
                if (!IsFarFromTowns(px, pz, 105f)) continue;
                PlaceTree(root, new Vector3(px, 0f, pz), rng);
                placed++;
            }
        }

        private static bool IsFarFromTowns(float x, float z, float gap)
        {
            for (int i = 0; i < s_spots.Count; i++)
            {
                float dx = s_spots[i].x - x;
                float dz = s_spots[i].z - z;
                if (dx * dx + dz * dz < gap * gap) return false;
            }
            return true;
        }

        private void PlaceTree(Transform root, Vector3 p, System.Random rng)
        {
            GameObject prefab = treePrefabs[rng.Next(treePrefabs.Length)];
            if (prefab == null) return;
            p.y = GroundHeight(p.x, p.z) - 0.05f;
            var go = Instantiate(prefab, p, Quaternion.Euler(0f, (float)rng.NextDouble() * 360f, 0f), root);
            float sc = 0.8f + (float)rng.NextDouble() * 0.55f;
            go.transform.localScale = go.transform.localScale * sc;
        }

        private void BuildCapitalGate(Transform world)
        {
            var root = new GameObject("CapitalGate").transform;
            root.SetParent(world, false);

            var stone = MapMaterials.Get("stone_light");
            var pave = MapMaterials.Get("cobble");
            var dark = MapMaterials.Get("stone_dark");

            // City floor: 300 m radius, top flush with the grass (a raised disc with a
            // kerb lip read as a coin lying on the field). The outer wall hides the rim,
            // so there is no visible edge at all.
            const float plazaR = 300f;
            Cyl(root, "Plaza", new Vector3(0f, -0.58f, 0f), new Vector3(plazaR * 2f, 0.6f, plazaR * 2f), pave, 0f, false);

            // Gate at capital scale, set INTO the city wall (r=298) so the arch is a real
            // tunnel with the city visible through it: 20 m clear opening, 30 m towers.
            const float gateZ = -296f;
            const float towerH = 30f;
            const float openHalf = 10f;
            const float pierW = 13f;
            const float pierCx = openHalf + pierW * 0.5f;

            Box(root, "GatePierL", new Vector3(-pierCx, towerH * 0.5f, gateZ), new Vector3(pierW, towerH, 16f), stone, 0f);
            Box(root, "GatePierR", new Vector3(pierCx, towerH * 0.5f, gateZ), new Vector3(pierW, towerH, 16f), stone, 0f);
            Box(root, "GateCapL", new Vector3(-pierCx, towerH + 0.9f, gateZ), new Vector3(pierW + 2.2f, 1.8f, 18.2f), dark, 0f);
            Box(root, "GateCapR", new Vector3(pierCx, towerH + 0.9f, gateZ), new Vector3(pierW + 2.2f, 1.8f, 18.2f), dark, 0f);

            // Machicolation band + merlons on each pier
            for (int i = 0; i < 5; i++)
            {
                float mx = -pierCx - 6f + i * 3f;
                Box(root, "MerlonL_" + i, new Vector3(mx, towerH + 3.4f, gateZ), new Vector3(1.7f, 3.0f, 3.2f), stone, 0f, false);
                Box(root, "MerlonR_" + i, new Vector3(-mx, towerH + 3.4f, gateZ), new Vector3(1.7f, 3.0f, 3.2f), stone, 0f, false);
            }

            // Arch: 23 RADIAL voussoirs on a 10 m semicircle springing at 13 m, so the
            // crown clears 23 m. The first version placed AXIS-ALIGNED cubes on the arc
            // without rolling them, which left sawtooth steps and slivers of sky between
            // the joints - at 44 m that is the first thing anyone sees. Each stone is now
            // rolled to a - its local +X is the radial direction - and the ring is embedded
            // in a solid spandrel, so the soffit is one continuous curve.
            const float archR = openHalf;
            const float springY = 13f;
            const float vousThick = 2.9f;
            int vousN = 23;
            // Each voussoir's width is the even arc division: the old fixed 2.46 m on a ring of only
            // 15 blocks could not match the arc, and the crown was stretched into a 180 px flat top
            // (the review: "trapezoid, not a round arch").
            float vousWide = Mathf.PI * (archR + vousThick * 0.5f) / (vousN - 1) * 0.97f;
            for (int i = 0; i < vousN; i++)
            {
                float a = Mathf.PI * i / (vousN - 1);
                float rMid = archR + vousThick * 0.5f;
                var c = new Vector3(Mathf.Cos(a) * rMid, springY + Mathf.Sin(a) * rMid, gateZ);
                var vgo = Box(root, "Arch_" + i, c, new Vector3(vousThick, vousWide, 16.4f), stone, 0f, false);
                vgo.transform.localRotation = Quaternion.Euler(0f, 0f, a * Mathf.Rad2Deg);
            }
            // Keystone: a slightly proud block at the crown, 0.35 m deeper than the voussoirs.
            Box(root, "ArchKeystone", new Vector3(0f, springY + archR + vousThick * 0.5f, gateZ),
                new Vector3(vousThick + 0.7f, vousWide * 1.9f, 16.4f), dark, 0f, false);

            // Spandrel: the solid wall the arch is cut into. It has to reach the tower caps
            // (30 m) - the old 2.6 m lintel floating at 25 m left a 3.6 m slit of sky over
            // the crown.
            Box(root, "GateSpandrel", new Vector3(0f, 26.5f, gateZ),
                new Vector3(openHalf * 2f + 7f, 7.5f, 16.4f), stone, 0f);
            // String course over the arch, reads as a built detail rather than a seam.
            Box(root, "GateArchivolt", new Vector3(0f, springY + archR, gateZ),
                new Vector3(openHalf * 2f + 9f, 0.9f, 17.2f), dark, 0f, false);

            // Short wing walls tie the gatehouse into the ring wall; the ring itself is
            // built by BuildCityRing with a gap where the gate stands.
            for (int s = -1; s <= 1; s += 2)
            {
                Box(root, "GateWing" + (s > 0 ? "R" : "L"),
                    new Vector3(s * (pierCx + pierW * 0.5f + 9f), 11f, gateZ),
                    new Vector3(18f, 22f, 10f), stone, 0f);
            }

            ScenePortal.Create(root, new Vector3(0f, 0.2f, gateZ),
                MapId.AsuraCapital, "start", "\u738b\u90fd \u963f\u5c14\u65af", 180f);
        }

        /// <summary>
        /// The walled city behind the gate. Without it the gate was a free-standing wall
        /// stub standing on paving, and through the arch you saw empty meadow - which is
        /// exactly what "no city" looks like from outside. This builds the enclosure, the
        /// tower rhythm, a keep silhouette and enough roof mass to fill the gate view.
        /// </summary>
        private void BuildCityRing(Transform world, System.Random rng)
        {
            var root = new GameObject("CapitalCity").transform;
            root.SetParent(world, false);

            var stone = MapMaterials.Get("stone_light");
            var dark = MapMaterials.Get("stone_dark");
            Material[] roofs =
            {
                MapMaterials.Get("roof_terracotta"), MapMaterials.Get("roof_slate"),
                MapMaterials.Get("roof_burgundy"), MapMaterials.Get("roof_thatch"),
            };
            var plaster = MapMaterials.Get("plaster_cream");

            const float wallR = 298f;
            const float wallH = 22f;
            const float wallD = 7f;
            const int blocks = 96;
            float arc = 2f * Mathf.PI * wallR / blocks;

            for (int i = 0; i < blocks; i++)
            {
                float a = i / (float)blocks * Mathf.PI * 2f;
                // Leave a gap for the gate at -90 degrees (south).
                float da = Mathf.DeltaAngle(a * Mathf.Rad2Deg, -90f) * Mathf.Deg2Rad;
                if (Mathf.Abs(da) < 0.085f) continue;

                var p = new Vector3(Mathf.Cos(a) * wallR, wallH * 0.5f, Mathf.Sin(a) * wallR);
                Box(root, "Wall_" + i, p, new Vector3(arc + 0.6f, wallH, wallD), stone, -a * Mathf.Rad2Deg);
                // Parapet band instead of separate merlon cubes: 96 combs of floating
                // boxes read as kitbash at every distance.
                var pp = new Vector3(Mathf.Cos(a) * (wallR - 0.9f), wallH + 1.3f, Mathf.Sin(a) * (wallR - 0.9f));
                Box(root, "Parapet_" + i, pp, new Vector3(arc + 0.6f, 2.6f, 3.2f), dark, -a * Mathf.Rad2Deg, false);
            }

            // Tower rhythm: 12 towers unevenly spaced, so the wall stops looking extruded.
            for (int i = 0; i < 12; i++)
            {
                float a = (i / 12f + (i % 3 == 0 ? 0.012f : -0.008f)) * Mathf.PI * 2f;
                float da = Mathf.DeltaAngle(a * Mathf.Rad2Deg, -90f) * Mathf.Deg2Rad;
                if (Mathf.Abs(da) < 0.20f) continue;
                float rr = 9.0f + (float)rng.NextDouble() * 2.4f;
                float hh = 34f + (float)rng.NextDouble() * 9f;
                var c = new Vector3(Mathf.Cos(a) * wallR, 0f, Mathf.Sin(a) * wallR);
                Cyl(root, "Tower_" + i, new Vector3(c.x, hh * 0.5f, c.z),
                    new Vector3(rr * 2f, hh * 0.5f, rr * 2f), stone, 0f);
                Cyl(root, "TowerCap_" + i, new Vector3(c.x, hh + 0.8f, c.z),
                    new Vector3(rr * 2.4f, 0.9f, rr * 2.4f), dark, 0f, false);
                Cyl(root, "TowerRoof_" + i, new Vector3(c.x, hh + 5.4f, c.z),
                    new Vector3(rr * 2.3f, 3.6f, rr * 2.3f), roofs[i % roofs.Length], 0f, false);
            }

            // Keep silhouette on the north side: the thing you see over the wall.
            var keep = new Vector3(0f, 0f, 205f);
            Box(root, "KeepBase", new Vector3(keep.x, 17f, keep.z), new Vector3(78f, 34f, 62f), stone, 0f);
            Box(root, "KeepUpper", new Vector3(keep.x, 42f, keep.z), new Vector3(52f, 22f, 44f), stone, 0f);
            Box(root, "KeepCrown", new Vector3(keep.x, 57f, keep.z), new Vector3(34f, 10f, 30f), dark, 0f, false);
            for (int sx = -1; sx <= 1; sx += 2)
            {
                for (int sz = -1; sz <= 1; sz += 2)
                {
                    Cyl(root, "KeepTurret" + sx + "" + sz,
                        new Vector3(keep.x + sx * 34f, 26f, keep.z + sz * 27f),
                        new Vector3(11f, 13f, 11f), stone, 0f);
                    Cyl(root, "KeepTurretRoof" + sx + "" + sz,
                        new Vector3(keep.x + sx * 34f, 42f, keep.z + sz * 27f),
                        new Vector3(13f, 6f, 13f), roofs[0], 0f, false);
                }
            }

            // Roof mass inside the walls. The first pass filled this with 300 boxes and
            // the aerial read was "grey cuboids with a coloured slab on top" - correct
            // scale, wrong silhouette. Each imported kit house is ONE merged mesh with
            // per-slot palette materials, so a real gabled house costs the same one
            // renderer a box did: use them everywhere and keep boxes only as a fallback
            // when no prefab is wired (e.g. a scene built before this field existed).
            int houses = 300;
            int placed = 0;
            int guard = 0;
            int prefabHouses = 0;
            bool usePrefabs = housePrefabs != null && housePrefabs.Length > 0;
            while (placed < houses && guard < houses * 12)
            {
                guard++;
                float ang = (float)rng.NextDouble() * Mathf.PI * 2f;
                float rr = 26f + (float)rng.NextDouble() * (wallR - 52f);
                float px = Mathf.Cos(ang) * rr;
                float pz = Mathf.Sin(ang) * rr;

                // Main avenue: keep |x| < 13 clear from the gate to the keep.
                if (Mathf.Abs(px) < 15f && pz < 150f) continue;
                // Central square around the origin
                if (rr < 40f) continue;
                // Keep apron
                if (Mathf.Abs(px) < 52f && pz > 150f) continue;

                float yaw = ang * Mathf.Rad2Deg + 90f + (float)rng.NextDouble() * 8f - 4f;
                if (usePrefabs)
                {
                    var prefab = housePrefabs[rng.Next(housePrefabs.Length)];
                    if (prefab != null)
                    {
                        var go = Instantiate(prefab, new Vector3(px, 0f, pz),
                            Quaternion.Euler(0f, yaw, 0f), root);
                        go.name = "House_" + placed;
                        float s = 1.15f + (float)rng.NextDouble() * 0.95f;
                        go.transform.localScale = new Vector3(s, s, s);
                        prefabHouses++;
                        placed++;
                        continue;
                    }
                }

                float w = 8f + (float)rng.NextDouble() * 11f;
                float d = 8f + (float)rng.NextDouble() * 11f;
                float h = 7f + (float)rng.NextDouble() * 8f;
                Material wallMat = rng.NextDouble() < 0.55 ? plaster : stone;
                Box(root, "House_" + placed, new Vector3(px, h * 0.5f, pz), new Vector3(w, h, d), wallMat,
                    yaw, false);
                Box(root, "Roof_" + placed, new Vector3(px, h + 1.1f, pz), new Vector3(w + 1.2f, 2.2f, d + 1.2f),
                    roofs[rng.Next(roofs.Length)], yaw, false);
                placed++;
            }

            Debug.Log("[KingdomWorld] capital wall blocks + houses=" + placed + " prefab=" + prefabHouses);
        }

        protected override void BuildSystems(Transform world)
        {
            if (GetComponent<KingdomAtmosphere>() == null)
                gameObject.AddComponent<KingdomAtmosphere>();

            // Weather and air (overworld): a clear morning by default, windy with fast clouds and
            // long atmospheric perspective.
            if (GetComponent<KingdomWeather>() == null)
            {
                var w = gameObject.AddComponent<KingdomWeather>();
                w.weather = SkyWeather.Clear;
                w.hourOfDay = 9.5f;
            }

            // Minimap: the user asked "otherwise I have no idea where I am". Reuse the town spots
            // computed while building the map - no second camera pass, because re-rendering a 3 km
            // scene just for the minimap is far too expensive.
            if (GetComponent<MinimapHud>() == null)
            {
                var hud = gameObject.AddComponent<MinimapHud>();
                hud.mode = MinimapHud.Mode.World;
                hud.worldHalf = 1500f;
                hud.textureSize = 512;
                hud.panelSize = 208f;
                if (s_spots != null && s_spots.Count > 0)
                {
                    hud.towns = s_spots.ToArray();
                    var to = new Vector3[hud.towns.Length];
                    for (int i = 0; i < to.Length; i++) to[i] = Vector3.zero;
                    hud.roadsTo = to;
                }
            }
        }

        protected override Vector3 ResolveSpawn(string spawnId)
        {
            // Spawn Y must follow the terrain: the ground plane is not y=0 - the surface at z=-470
            // is 5.9 m high, and a hard-coded 0.2 would spawn the player 6 m under the ground and
            // drop the CharacterController out of the world (measured y=-23912).
            var p = CapitalSpawn;
            p.y = GroundHeight(p.x, p.z) + 0.35f;
            return p;
        }
    }

    /// <summary>
    /// Atmosphere for the 3km overworld: far fog, trilight ambient, procedural sky,
    /// long shadow distance, wide camera far plane. Runs in Start so Camera.main exists.
    /// </summary>
    public class KingdomAtmosphere : MonoBehaviour
    {
        public float fogStart = 700f;
        public float fogEnd = 3400f;
        public float farClip = 4200f;

        private void Start()
        {
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Linear;
            RenderSettings.fogStartDistance = fogStart;
            RenderSettings.fogEndDistance = fogEnd;
            RenderSettings.fogColor = new Color(0.66f, 0.755f, 0.875f);

            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.58f, 0.65f, 0.80f);
            RenderSettings.ambientEquatorColor = new Color(0.50f, 0.48f, 0.44f);
            RenderSettings.ambientGroundColor = new Color(0.30f, 0.28f, 0.24f);

            SetupSky();

            // Default shadow distance (40-50m) means no wall ever casts a visible shadow.
            QualitySettings.shadowDistance = 220f;

            var cam = Camera.main;
            if (cam != null)
            {
                cam.farClipPlane = farClip;
                cam.nearClipPlane = 0.3f;
                cam.clearFlags = CameraClearFlags.Skybox;
            }

            // TopDownCameraRig switches the camera to a plain skybox in its own Start (a minimap-
            // scene setting) and the order of the two Starts is not defined. Force the rig switch
            // on here and re-assert it for the first few frames, otherwise the 3 km horizon crashes
            // into a dead colour plate (measured: sky 55-60 levels darker than the ridges).
            var rig = Object.FindFirstObjectByType<TopDownCameraRig>();
            if (rig != null)
            {
                rig.UseSkybox = true;
                // The camera's far plane is recomputed every frame from distance*2.5 (= 60), so
                // only raising the lower bound keeps the 4.2 km far plane.
                rig.minFarClip = farClip;
            }
            StartCoroutine(EnforceSkybox(6));
        }

        private System.Collections.IEnumerator EnforceSkybox(int frames)
        {
            for (int i = 0; i < frames; i++)
            {
                var cam = Camera.main;
                if (cam != null && RenderSettings.skybox != null)
                {
                    cam.clearFlags = CameraClearFlags.Skybox;
                    cam.backgroundColor = new Color(0.66f, 0.78f, 0.90f);
                }
                // Keep re-asserting far as well: this Start may run before the rig's Start, in
                // which case the lookup above returned null; the rig Update then recomputes far
                // from distance*2.5 = 60 m and the 3 km map shrinks to a small patch in front of
                // the camera.
                var rig = Object.FindFirstObjectByType<TopDownCameraRig>();
                if (rig != null && rig.minFarClip < farClip) rig.minFarClip = farClip;
                if (cam != null && cam.farClipPlane < farClip * 0.9f) cam.farClipPlane = farClip;
                yield return null;
            }
        }

        /// <summary>Procedural skybox wired to the scene sun; falls back to a solid colour.</summary>
        public static void SetupSky()
        {
            var sh = Shader.Find("Skybox/Procedural");
            if (sh != null)
            {
                var m = new Material(sh) { name = "KingdomSky" };
                m.SetFloat("_SunSize", 0.045f);
                m.SetFloat("_SunSizeConvergence", 3f);
                m.SetFloat("_AtmosphereThickness", 0.85f);
                m.SetColor("_SkyTint", new Color(0.52f, 0.62f, 0.82f));
                m.SetColor("_GroundColor", new Color(0.42f, 0.44f, 0.40f));
                m.SetFloat("_Exposure", 1.15f);
                RenderSettings.skybox = m;

                Light sun = null;
                var lights = Object.FindObjectsByType<Light>(FindObjectsSortMode.None);
                for (int i = 0; i < lights.Length; i++)
                {
                    if (lights[i].type == LightType.Directional) { sun = lights[i]; break; }
                }
                RenderSettings.sun = sun;
                DynamicGI.UpdateEnvironment();
                return;
            }

            var cam = Camera.main;
            if (cam != null)
            {
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = new Color(0.55f, 0.67f, 0.85f);
            }
        }
    }
}
