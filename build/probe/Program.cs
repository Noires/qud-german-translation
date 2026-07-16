using System;
using System.IO;
using System.Linq;
using System.Reflection;

class P {
  static void Main() {
    string mgd = @"C:\Program Files (x86)\Steam\steamapps\common\Caves of Qud\CoQ_Data\Managed";
    var rt = new PathAssemblyResolver(Directory.GetFiles(mgd, "*.dll"));
    using var mlc = new MetadataLoadContext(rt);
    var asm = mlc.LoadFromAssemblyPath(Path.Combine(mgd, "Assembly-CSharp.dll"));
    // localization + message pipeline entry points
    foreach (var tn in new[] { "XRL.Language.Strings", "XRL.Language.GameText", "XRL.Messages.MessageQueue", "XRL.UI.Popup" }) {
      var t = asm.GetType(tn);
      if (t == null) { Console.WriteLine("NOT FOUND: "+tn); continue; }
      Console.WriteLine("\n===== " + tn + " =====");
      foreach (var m in t.GetMethods(BindingFlags.Public|BindingFlags.Static|BindingFlags.Instance|BindingFlags.DeclaredOnly)
                         .Where(m => m.Name.Contains("Get")||m.Name.Contains("Replace")||m.Name.Contains("Localiz")||m.Name.Contains("Message")||m.Name.Contains("Translate")||m.Name.Contains("Show"))) {
        var ps = string.Join(", ", m.GetParameters().Take(5).Select(p => p.ParameterType.Name+" "+p.Name));
        Console.WriteLine($"  {m.ReturnType.Name} {m.Name}({ps})");
      }
    }
  }
}
