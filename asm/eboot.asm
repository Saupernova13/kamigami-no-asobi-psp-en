; EBOOT patches for English text. Assemble with armips against the static EBOOT made by
; tools/prx.py (module fixed at 0x08804000, file offset 0xC0):
;   armips asm/eboot.asm -strequ IN <static EBOOT.ELF> -strequ OUT <patched ELF>
;
; Same problem as Utapri's NIS engine: the script VM hands single-byte (ASCII) characters
; to the window with a zero second byte, the 2-byte renderers stop at a zero byte, and the
; window lays glyphs out at a fixed 16px. The glyph lookup (FUN_088a216c) ignores the
; second byte for 0x20-0x7E, so ASCII stored as (c, 0x01) draws correctly; the window then
; needs a real advance and the glyph shifted left by its bearing.

.psp
.open IN, OUT, 0x08804000 - 0xC0

LETTER_SPACING equ 1

PercentForSize  equ 0x08889ac4   ; (size step) -> percent, as used by the fixed advance
FixedAdvance    equ 0x0888a998   ; original: full-width advance for a size step
WidthFontA      equ 0x088a1690   ; (code, percent) -> ink width, FontA metrics
GlyphIndex      equ 0x088a2128   ; code -> font table index
FontAFtdPtr     equ 0x08996934   ; -> FontA.ftd (u16 count, then s8 left/right per glyph)

; --- script VM, single-byte text path (FUN_08871678) ----------------------------------
.org 0x08875228                 ; second byte passed to the emitter FUN_08862f20 (window
    li      a2, 1               ; buffer, alternate buffer and backlog all take it from here)

; --- message window layout (FUN_0887dcd8, s0 = glyph table at 0x089ad410) -------------
.org 0x0887dd98                 ; was: jal FixedAdvance
    jal     AsciiAdvance

; --- code cave: FUN_088a7b80 has no callers, jumps, pointers or address constructions --
.org 0x088a7b80
.area 1076
; a0 = signed size step, a1 = 0, caller's s0 = glyph table (count at +0x1aa0,
; entries of 10 bytes: s16 x, s16 y, u16 code, ...). Returns v0 = advance.
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
    sw      s2, 24(sp)
    jal     PercentForSize      ; a0 = size step
    move    s1, t6
    move    s2, v0              ; percent
    lhu     a0, 4(s1)
    andi    a0, a0, 0xff
    jal     WidthFontA
    move    a1, s2
    sw      v0, 28(sp)
    lhu     a0, 4(s1)
    jal     GlyphIndex
    andi    a0, a0, 0xff
    lui     t9, FontAFtdPtr >> 16
    lw      t9, FontAFtdPtr & 0xffff(t9)
    sll     v0, v0, 1
    addu    t9, t9, v0
    lb      t8, 2(t9)           ; left bearing, 18px-cell units
    sll     t8, t8, 4           ; * 16/18 * percent/100
    mult    t8, s2
    mflo    t8
    li      t9, 1800
    div     t8, t9
    mflo    t8
    lhu     t9, 0(s1)
    subu    t9, t9, t8
    sh      t9, 0(s1)           ; draw the glyph left by its bearing
    lw      v0, 28(sp)
    addiu   v0, v0, LETTER_SPACING
    lw      s2, 24(sp)
    lw      s1, 20(sp)
    lw      ra, 16(sp)
    jr      ra
    addiu   sp, sp, 32
@@fixed:
    j       FixedAdvance
    nop
.endarea

.close
