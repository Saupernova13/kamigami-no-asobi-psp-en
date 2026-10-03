; EBOOT patches for English text. Assemble with armips against the static EBOOT made by
; tools/prx.py (module fixed at 0x08804000, file offset 0xC0):
;   armips asm/eboot.asm -strequ IN <static EBOOT.ELF> -strequ OUT <patched ELF>
;
; Same problem as Utapri's NIS engine: the script VM hands single-byte (ASCII) characters
; to the window with a zero second byte, the 2-byte renderers stop at a zero byte, and the
; window lays glyphs out at a fixed 16px. The glyph lookup (FUN_088a216c) ignores the
; second byte for 0x20-0x7E, so ASCII stored as (c, 0x01) draws correctly; the window then
; needs a real advance (the draw itself already offsets each glyph by its left bearing).

.psp
.open IN, OUT, 0x08804000 - 0xC0

LETTER_SPACING equ 1

PercentForSize  equ 0x08889ac4   ; (size step) -> percent, as used by the fixed advance
FixedAdvance    equ 0x0888a998   ; original: full-width advance for a size step
WidthFontA      equ 0x088a1690   ; (code, percent) -> ink width, FontA metrics

; --- script VM, single-byte text path (FUN_08871678) ----------------------------------
.org 0x08875228                 ; second byte passed to the emitter FUN_08862f20 (window
    li      a2, 1               ; buffer, alternate buffer and backlog all take it from here)

; --- message window layout (FUN_0887dcd8, s0 = glyph table at 0x089ad410) -------------
.org 0x0887dd98                 ; was: jal FixedAdvance
    jal     AsciiAdvance

; --- UI string renderers: draw ASCII with the proportional branch ----------------------
; These -O0 loops re-load a fixed/proportional mode flag from the stack before each branch:
;   lw a0, MODE(sp) / bne a0, zero, FIXED / nop
; becomes
;   jal stub / nop / bne v0, zero, FIXED
; where the stub returns 0 (proportional) for an ASCII character and the flag otherwise.
; UI strings store ASCII as (c, 0x01) pairs because these loops always step 2 bytes.
; The instruction after each site always reloads a0, so it is safe in the new delay slot,
; and every branch target reloads a0 too.
.macro ModeCheck, site, stub, target
    .org site
        jal     stub
        nop
        bne     v0, zero, target
.endmacro

ModeCheck 0x08889bd4, ModeCode18_38, 0x08889c10    ; FUN_08889b2c
ModeCheck 0x08889c44, ModeCode18_38, 0x08889c88
ModeCheck 0x08889c68, ModeCode18_38, 0x08889b88
ModeCheck 0x08889d40, ModePtr18_20, 0x08889d80     ; FUN_08889cbc
ModeCheck 0x08889db8, ModePtr18_20, 0x08889dec
ModeCheck 0x0888a0b0, ModePtr18_20, 0x0888a0f0     ; FUN_0888a028
ModeCheck 0x0888a128, ModePtr18_20, 0x0888a154
ModeCheck 0x0888ac20, ModeCode1c_3c, 0x0888ac5c    ; FUN_0888ab70
ModeCheck 0x0888ac90, ModeCode1c_3c, 0x0888acbc
ModeCheck 0x0888ace0, ModeCode1c_3c, 0x0888abd4
ModeCheck 0x0888ada4, ModePtr1c_20, 0x0888ade4     ; FUN_0888ad18
ModeCheck 0x0888ae1c, ModePtr1c_20, 0x0888ae48
ModeCheck 0x0888ae70, ModePtr1c_20, 0x0888ae90
ModeCheck 0x08890650, ModeCode1c_50, 0x0889068c    ; FUN_08890550
ModeCheck 0x0889076c, ModeCode1c_50, 0x0889079c

; --- code cave: FUN_088a7b80 has no callers, jumps, pointers or address constructions --
.org 0x088a7b80
.area 0x200                     ; code; the rest of the cave is a string heap (tools/build.py)

; Mode stubs run on the caller's stack frame (no frame of their own).
; ModeCode: current char is a halfword at CODE(sp). ModePtr: string pointer at PTR(sp).
.macro ModeCode, name, mode, code
name:
    lw      v0, mode(sp)
    beq     v0, zero, @@done
    lhu     t9, code(sp)
    andi    t9, t9, 0xff
    addiu   t9, t9, -0x20
    sltiu   t9, t9, 0x5f        ; 0x20-0x7E
    beq     t9, zero, @@done
    nop
    move    v0, zero
@@done:
    jr      ra
    nop
.endmacro
.macro ModePtr, name, mode, ptr
name:
    lw      v0, mode(sp)
    beq     v0, zero, @@done
    lw      t9, ptr(sp)
    lbu     t9, 0(t9)
    andi    t9, t9, 0xff
    addiu   t9, t9, -0x20
    sltiu   t9, t9, 0x5f        ; 0x20-0x7E
    beq     t9, zero, @@done
    nop
    move    v0, zero
@@done:
    jr      ra
    nop
.endmacro
ModeCode ModeCode18_38, 0x18, 0x38
ModePtr  ModePtr18_20, 0x18, 0x20
ModeCode ModeCode1c_3c, 0x1c, 0x3c
ModePtr  ModePtr1c_20, 0x1c, 0x20
ModeCode ModeCode1c_50, 0x1c, 0x50

; a0 = signed size step, a1 = 0, caller's s0 = glyph table (count at +0x1aa0,
; entries of 10 bytes: s16 x, s16 y, u16 code, ...). Returns v0 = advance: the glyph's
; ink width for an ASCII unit (the draw already offsets glyphs by their left bearing),
; the fixed full-width advance otherwise.
AsciiAdvance:
    lw      t8, 0x1aa0(s0)      ; index of the entry just written
    sll     t7, t8, 2
    addu    t7, t7, t8
    sll     t7, t7, 1
    addu    t6, t7, s0          ; entry
    lhu     t7, 4(t6)
    srl     t8, t7, 8
    li      t9, 1
    bne     t8, t9, @@fixed
    nop
    addiu   sp, sp, -32
    sw      ra, 16(sp)
    sw      s1, 20(sp)
    jal     PercentForSize      ; a0 = size step
    move    s1, t6
    lhu     a0, 4(s1)
    andi    a0, a0, 0xff
    jal     WidthFontA
    move    a1, v0              ; percent
    addiu   v0, v0, LETTER_SPACING
    lw      s1, 20(sp)
    lw      ra, 16(sp)
    jr      ra
    addiu   sp, sp, 32
@@fixed:
    j       FixedAdvance
    nop
.endarea

.org 0x088a7b80 + 0x200
.area 1076 - 0x200, 0           ; STRING_HEAP: filled by the build
.endarea

.close
