using System.Collections.Generic;
using BusReplay.Core;
using UnityEngine;
using UnityEngine.Rendering;

namespace BusReplay
{
    /// <summary>Buduje statyczna geometrie sieci: plansze, wstegi tras i kolka przystankow.</summary>
    public static class NetworkRenderer
    {
        public const float RouteWidth = 6f;
        public const float StopDiameter = 12f;
        public const int StopSides = 16;
        public const float GroundMargin = 1000f;

        public static GameObject Build(NetworkData net, Material ground, Material route, Material stop)
        {
            var root = new GameObject("Network");
            AddMeshObject(root, "Ground", BuildGround(net.Bbox), ground);
            AddMeshObject(root, "Routes", BuildRoutes(net.Segments), route);
            AddMeshObject(root, "Stops", BuildStops(net.Stops), stop);
            return root;
        }

        static void AddMeshObject(GameObject parent, string name, Mesh mesh, Material mat)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent.transform, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = ShadowCastingMode.Off;
            mr.receiveShadows = false;
        }

        static Mesh BuildGround(Rect bbox)
        {
            float x0 = bbox.xMin - GroundMargin, x1 = bbox.xMax + GroundMargin;
            float z0 = bbox.yMin - GroundMargin, z1 = bbox.yMax + GroundMargin;
            var mesh = new Mesh { name = "Ground" };
            mesh.vertices = new[]
            {
                new Vector3(x0, 0, z0), new Vector3(x0, 0, z1),
                new Vector3(x1, 0, z1), new Vector3(x1, 0, z0),
            };
            mesh.triangles = new[] { 0, 1, 2, 0, 2, 3 };
            mesh.RecalculateBounds();
            return mesh;
        }

        static Mesh BuildRoutes(NetworkSegment[] segments)
        {
            var verts = new List<Vector3>();
            var tris = new List<int>();
            const float half = RouteWidth * 0.5f;
            foreach (var seg in segments)
            {
                var p = seg.Points;
                for (int i = 0; i + 1 < p.Length; i++)
                {
                    Vector2 d = p[i + 1] - p[i];
                    float len = d.magnitude;
                    if (len < 1e-3f) continue;
                    d /= len;
                    Vector2 r = new Vector2(d.y, -d.x) * half;
                    int b = verts.Count;
                    verts.Add(new Vector3(p[i].x - r.x, 0.05f, p[i].y - r.y));
                    verts.Add(new Vector3(p[i + 1].x - r.x, 0.05f, p[i + 1].y - r.y));
                    verts.Add(new Vector3(p[i + 1].x + r.x, 0.05f, p[i + 1].y + r.y));
                    verts.Add(new Vector3(p[i].x + r.x, 0.05f, p[i].y + r.y));
                    tris.Add(b); tris.Add(b + 1); tris.Add(b + 2);
                    tris.Add(b); tris.Add(b + 2); tris.Add(b + 3);
                }
            }
            var mesh = new Mesh { name = "Routes", indexFormat = IndexFormat.UInt32 };
            mesh.SetVertices(verts);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateBounds();
            return mesh;
        }

        static Mesh BuildStops(NetworkStop[] stops)
        {
            var verts = new List<Vector3>(stops.Length * (StopSides + 1));
            var tris = new List<int>(stops.Length * StopSides * 3);
            const float rad = StopDiameter * 0.5f;
            foreach (var s in stops)
            {
                int b = verts.Count;
                verts.Add(new Vector3(s.Pos.x, 0.1f, s.Pos.y));
                for (int i = 0; i < StopSides; i++)
                {
                    float a = i * Mathf.PI * 2f / StopSides;
                    verts.Add(new Vector3(s.Pos.x + Mathf.Cos(a) * rad, 0.1f, s.Pos.y + Mathf.Sin(a) * rad));
                }
                for (int i = 0; i < StopSides; i++)
                {
                    tris.Add(b);
                    tris.Add(b + 1 + (i + 1) % StopSides);
                    tris.Add(b + 1 + i);
                }
            }
            var mesh = new Mesh { name = "Stops", indexFormat = IndexFormat.UInt32 };
            mesh.SetVertices(verts);
            mesh.SetTriangles(tris, 0);
            mesh.RecalculateBounds();
            return mesh;
        }
    }
}
