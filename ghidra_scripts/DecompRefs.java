// Decompile every function that references the given strings or addresses.
// Args: outfile token... (token = literal string to find, or 0xADDR for a function/address)
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.mem.*;
import java.io.*;
import java.util.*;

public class DecompRefs extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        PrintWriter out = new PrintWriter(new FileWriter(args[0]));
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        Set<Function> done = new LinkedHashSet<>();
        for (int i = 1; i < args.length; i++) {
            String tok = args[i];
            List<Address> targets = new ArrayList<>();
            if (tok.startsWith("0x")) {
                targets.add(toAddr(Long.parseLong(tok.substring(2), 16)));
            } else {
                byte[] pat = (tok + "\0").getBytes("US-ASCII");
                Address a = currentProgram.getMinAddress();
                while ((a = currentProgram.getMemory().findBytes(a, pat, null, true, monitor)) != null) {
                    targets.add(a); a = a.add(1);
                }
            }
            for (Address t : targets) {
                out.println("// ===== token " + tok + " @ " + t);
                Function self = getFunctionContaining(t);
                List<Function> fs = new ArrayList<>();
                if (self != null) fs.add(self);
                for (Reference r : getReferencesTo(t)) {
                    Function f = getFunctionContaining(r.getFromAddress());
                    out.println("//   ref from " + r.getFromAddress() + " in " + (f == null ? "?" : f.getName()));
                    if (f != null) fs.add(f);
                }
                for (Function f : fs) {
                    if (!done.add(f)) continue;
                    DecompileResults res = di.decompileFunction(f, 60, monitor);
                    out.println("// ----- " + f.getName() + " @ " + f.getEntryPoint());
                    if (res.decompileCompleted()) out.println(res.getDecompiledFunction().getC());
                    else out.println("// decompile failed: " + res.getErrorMessage());
                }
            }
        }
        out.close();
    }
}
