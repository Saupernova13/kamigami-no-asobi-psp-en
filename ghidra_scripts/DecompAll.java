// Decompile every function in the program into one C file (for grepping offline).
// Args: outfile
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;

public class DecompAll extends GhidraScript {
    public void run() throws Exception {
        PrintWriter out = new PrintWriter(new FileWriter(getScriptArgs()[0]));
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (f.isThunk()) continue;
            DecompileResults res = di.decompileFunction(f, 60, monitor);
            out.println("// ===== " + f.getName() + " @ " + f.getEntryPoint());
            if (res.decompileCompleted()) out.println(res.getDecompiledFunction().getC());
            else out.println("// decompile failed: " + res.getErrorMessage());
        }
        out.close();
    }
}
