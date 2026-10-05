// Dump disassembly of the functions at the given addresses.
// Args: outfile 0xADDR...
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.address.*;
import java.io.*;

public class DumpAsm extends GhidraScript {
    public void run() throws Exception {
        String[] args = getScriptArgs();
        PrintWriter out = new PrintWriter(new FileWriter(args[0]));
        Listing lst = currentProgram.getListing();
        for (int i = 1; i < args.length; i++) {
            Address a = toAddr(Long.parseLong(args[i].substring(2), 16));
            Function f = getFunctionContaining(a);
            out.println("// ===== " + (f == null ? "?" : f.getName()) + " " + (f == null ? "" : f.getBody().toString()));
            AddressSetView body = f.getBody();
            for (Instruction ins : lst.getInstructions(body, true)) {
                StringBuilder hex = new StringBuilder();
                for (byte b : ins.getBytes()) hex.append(String.format("%02x", b));
                out.println(ins.getAddress() + "  " + hex + "  " + ins.toString());
            }
        }
        out.close();
    }
}
