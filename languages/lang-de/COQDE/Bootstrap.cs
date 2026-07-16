using System;
using System.IO;
using System.Reflection;
using XRL;

namespace LanguagesOfQudGerman
{
    // Game-compiled loader. Caves of Qud compiles this file at mod init; it loads the
    // pre-built COQDE.dll by reflection and calls COQDE.COQDEMod.Init(). This mirrors the
    // Korean reference mod's COQKRLoader and sidesteps any uncertainty about whether a
    // language mod's CODE/ compilation applies Harmony patches (the DLL does its own).
    //
    // This is the ONLY .cs file shipped inside languages/lang-de/COQDE/ — the engine source
    // lives outside the mod (build/COQDE/) so the game does not also compile it and collide
    // with the loaded DLL's types.
    [HasModSensitiveStaticCache]
    public static class COQDELoader
    {
        private static readonly object LoadLock = new object();
        private static Assembly loaded;

        [ModSensitiveCacheInit]
        public static void Bootstrap()
        {
            try
            {
                Assembly assembly = GetOrLoadAssembly();
                Type modType = assembly.GetType("COQDE.COQDEMod");
                if (modType == null)
                    throw new InvalidOperationException("[QudDE] type COQDE.COQDEMod not found.");

                MethodInfo init = modType.GetMethod("Init", BindingFlags.Public | BindingFlags.Static);
                if (init == null)
                    throw new InvalidOperationException("[QudDE] method COQDEMod.Init not found.");

                init.Invoke(null, null);
                UnityEngine.Debug.Log("[QudDE] COQDE bootstrap complete.");
            }
            catch (Exception ex)
            {
                UnityEngine.Debug.LogError("[QudDE] COQDE bootstrap failed: " + ex);
            }
        }

        private static Assembly GetOrLoadAssembly()
        {
            lock (LoadLock)
            {
                if (loaded != null) return loaded;
                string dllPath = Path.Combine(ResolvePackagePath(), "COQDE.dll");
                if (!File.Exists(dllPath))
                    throw new FileNotFoundException("[QudDE] COQDE.dll not found.", dllPath);
                loaded = Assembly.LoadFrom(dllPath);
                return loaded;
            }
        }

        private static string ResolvePackagePath()
        {
            foreach (var mod in ModManager.Mods)
            {
                string languagePath = Path.Combine(mod.Path, "languages", "lang-de");
                string packagePath = Path.Combine(languagePath, "COQDE");
                if (File.Exists(Path.Combine(packagePath, "COQDE.dll"))) return packagePath;
                if (File.Exists(Path.Combine(languagePath, "COQDE.dll"))) return languagePath;
            }
            throw new InvalidOperationException("[QudDE] COQDE package folder not found.");
        }
    }
}
