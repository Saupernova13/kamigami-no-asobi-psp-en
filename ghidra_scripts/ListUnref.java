// List functions with no references (calls, jumps or data pointers) to their entry point.
// Args: outfile
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import java.io.*;

public class ListUnref extends GhidraScript {
    public void run() throws Exception {
        PrintWriter out = new PrintWriter(new FileWriter(getScriptArgs()[0]));
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (getReferencesTo(f.getEntryPoint()).length == 0) {
                long size = f.getBody().getNumAddresses();
                out.println(f.getEntryPoint() + " " + size + " " + f.getName());
            }
        }
        out.close();
    }
}
