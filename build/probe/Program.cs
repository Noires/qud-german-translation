using System;using System.IO;using System.Linq;using System.Reflection;
class P{static void Main(){
 string mgd=@"C:\Program Files (x86)\Steam\steamapps\common\Caves of Qud\CoQ_Data\Managed";
 using var mlc=new MetadataLoadContext(new PathAssemblyResolver(Directory.GetFiles(mgd,"*.dll")));
 var asm=mlc.LoadFromAssemblyPath(Path.Combine(mgd,"Assembly-CSharp.dll"));
 // BodyPartReplacers: exact VariableReplacer names
 var bpr=asm.GetType("XRL.World.Text.Delegates.BodyPartReplacers");
 Console.WriteLine("== BodyPartReplacers name/ordinalName ==");
 foreach(var m in bpr.GetMethods(BindingFlags.Public|BindingFlags.Static|BindingFlags.DeclaredOnly)){
   var at=m.GetCustomAttributesData().Where(a=>a.AttributeType.Name.StartsWith("VariableReplacer"));
   var nm=string.Join(",",at.SelectMany(a=>a.ConstructorArguments.SelectMany(c=>c.Value is System.Collections.ObjectModel.ReadOnlyCollection<CustomAttributeTypedArgument> col?col.Select(x=>x.Value?.ToString()):new[]{c.Value?.ToString()})).Where(s=>!string.IsNullOrEmpty(s)));
   if(m.Name=="Name"||m.Name=="OrdinalName") Console.WriteLine($"  {m.Name}: attrNames=[{nm}] hasAttr={at.Any()}");
 }
 // BodyPart: GetCardinalName / Laterality
 var bp=asm.GetType("XRL.World.Anatomy.BodyPart");
 Console.WriteLine("== BodyPart members ==");
 foreach(var m in bp.GetMethods(BindingFlags.Public|BindingFlags.Instance).Where(m=>m.Name.Contains("Cardinal")||m.Name.Contains("Ordinal")))
   Console.WriteLine($"  {m.ReturnType.Name} {m.Name}({string.Join(",",m.GetParameters().Select(p=>p.ParameterType.Name))})");
 var lp=bp.GetProperty("Laterality"); var lf=bp.GetField("Laterality");
 Console.WriteLine("  Laterality: "+(lp!=null?"prop "+lp.PropertyType.Name:lf!=null?"field "+lf.FieldType.Name:"?"));
 // Laterality.StripLateralityAdjective
 var lat=asm.GetType("XRL.World.Capabilities.Laterality");
 Console.WriteLine("== Laterality.StripLateralityAdjective ==");
 foreach(var m in lat.GetMethods(BindingFlags.Public|BindingFlags.Static).Where(m=>m.Name.Contains("Strip")))
   Console.WriteLine($"  {m.ReturnType.Name} {m.Name}({string.Join(",",m.GetParameters().Select(p=>p.ParameterType.Name+" "+p.Name))})");
}}
