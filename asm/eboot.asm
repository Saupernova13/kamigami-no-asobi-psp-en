; EBOOT patches for English text. Assemble with armips against the static EBOOT made by
; tools/prx.py (module fixed at 0x08804000, file offset 0xC0):
;   armips asm/eboot.asm -strequ IN <static EBOOT.ELF> -strequ OUT <patched ELF>
;
; The problem this solves: the script VM hands single-byte (ASCII) characters
; to the window with a zero second byte, the 2-byte renderers stop at a zero byte, and the
; window lays glyphs out at a fixed 16px. The glyph lookup (FUN_088a216c) ignores the
; second byte for 0x20-0x7E, so ASCII stored as (c, 0x01) draws correctly; the window then
; needs a real advance (the draw itself already offsets each glyph by its left bearing).

.psp
.open IN, OUT, 0x08804000 - 0xC0

LETTER_SPACING equ 1
UI_SPACING equ 1               ; UI loops' gap after a proportional glyph (originally 2)

PercentForSize  equ 0x08889ac4   ; (size step) -> percent, as used by the fixed advance
FixedAdvance    equ 0x0888a998   ; original: full-width advance for a size step
GlyphAdvance    equ 0x0888a910   ; (code, size step, fixed) -> advance
WidthFontA      equ 0x088a1690   ; (code, percent) -> ink width, FontA metrics
GlyphIndex      equ 0x088a2128   ; code -> font table index
FontAFtdPtr     equ 0x08996934   ; -> FontA.ftd (u16 count, then s8 left/right per glyph)

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

; --- UI width loops (used to centre and right-align strings): with the fixed flag set they
; count a full-width cell per unit, while the draw loops above now draw ASCII
; proportionally, so centred English drifted left. Same stubs: ASCII measures
; proportionally. Two shapes: "lw a0, MODE / bnez a0, X" and "lw a0, MODE / ori a1, 1 /
; bne a0, a1, X" (the ori stays in the delay slot; the stubs leave a1 alone).
.macro ModeCheckOne, site, stub, target
    .org site
        jal     stub
        ori     a1, zero, 1
        bne     v0, a1, target
.endmacro
ModeCheckOne 0x0888a844, ModeCode0c_1e, 0x0888a86c  ; FUN_0888a7b0
ModeCheckOne 0x0888a738, ModeCode0c_1e, 0x0888a760  ; FUN_0888a6a4
ModeCheck    0x0888a54c, ModeCode0c_1e, 0x0888a588  ; FUN_0888a4ac
ModeCheck    0x0888a588, ModeCode0c_1e, 0x0888a5b4
ModeCheckOne 0x0888a5e4, ModeCode0c_1e, 0x0888a660
ModeCheck    0x0888a660, ModeCode0c_1e, 0x0888a680
ModeCheck    0x08890868, ModeCode08_1c, 0x088908d0  ; FUN_088907dc

; --- name entry opens on the ABC page (FUN_0881567c, a1 = 0x08966304): mode 0
; hiragana, 1 katakana, 2 ABC, 3 kanji, kept at +0x33a and copied to +4. The two
; byte clears at +0xb6 and +0xb7 merge into one halfword store to make room.
.org 0x088156cc
    sh      zero, 0xb6(a1)
.org 0x088156e4
    ori     t0, zero, 2
    sb      t0, 0x33a(a1)
    sb      t0, 4(a1)

; --- UI letter spacing: the proportional branches of the draw loops and the matching
; width loops add 2 px after each glyph, loose for English. Same value in both, so
; centred text stays centred.
.org 0x08889c78                 ; FUN_08889b2c (help bar)
    addiu   a0, a0, UI_SPACING
.org 0x08889ddc                 ; FUN_08889cbc
    addiu   a0, a0, UI_SPACING
.org 0x0888acec                 ; FUN_0888ab70
    ori     a0, zero, UI_SPACING
.org 0x0888ae7c                 ; FUN_0888ad18
    ori     a0, zero, UI_SPACING
.org 0x0889078c                 ; FUN_08890550
    addiu   a0, a0, UI_SPACING
.org 0x0888a890                 ; width: FUN_0888a7b0
    ori     a0, zero, UI_SPACING
.org 0x0888a66c                 ; width: FUN_0888a4ac
    ori     a0, zero, UI_SPACING
.org 0x0888a784                 ; width: FUN_0888a6a4
    addiu   a0, a0, UI_SPACING
.org 0x088908c0                 ; width: FUN_088907dc
    addiu   a0, a0, UI_SPACING

; --- dictionary body (FUN_08813e58): one glyph at a time, advance from GlyphAdvance with
; fixed = 1, minus 2. The glyph itself goes through FUN_0888ab70, which the ModeCheck
; above already draws proportionally, so only the advance needs the ink width.
.org 0x08814094
    jal     DictAdvance

; Mythology Monologue body (FUN_088233c4) is the same loop.
.org 0x0882369c
    jal     DictAdvance

; --- choices (FUN_08871678 measures and lays out the labels, FUN_088753fc draws them):
; each glyph goes through FUN_0888a27c, then x moves by GlyphAdvance(code, -1, fixed 1),
; a full-width cell even for ASCII. Labels are (c, 0x01) pairs from the VM emitter.
.org 0x08872a00
    jal     ChoiceAdvance
.org 0x08872f60
    jal     ChoiceAdvance
.org 0x088734a8
    jal     ChoiceAdvance
.org 0x08875798
    jal     ChoiceAdvance

; --- code cave: FUN_088a7b80 has no callers, jumps, pointers or address constructions --
.org 0x088a7b80
.area 0x300                     ; code; the rest of the cave is a string heap (tools/build.py)

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
ModeCode ModeCode0c_1e, 0x0c, 0x1e
ModeCode ModeCode08_1c, 0x08, 0x1c

; a0 = signed size step, a1 = 0, caller's s0 = glyph table (count at +0x1aa0,
; entries of 10 bytes: s16 x, s16 y, u16 code = lead | second << 8, ...). Returns
; v0 = advance: the ink width for an ASCII unit (second byte 1) or a full-width letter
; or digit (82 4F-82 9A, what player names are typed in), the fixed full-width advance
; otherwise. The draw offsets ASCII glyphs by their left bearing itself; a full-width
; glyph is drawn at its cell origin, so its entry x moves left by the bearing here.
AsciiAdvance:
    lw      t8, 0x1aa0(s0)      ; index of the entry just written
    sll     t7, t8, 2
    addu    t7, t7, t8
    sll     t7, t7, 1
    addu    t6, t7, s0          ; entry
    lhu     t7, 4(t6)           ; code
    srl     t8, t7, 8
    li      t9, 1
    beq     t8, t9, @@measure
    andi    t9, t7, 0xff        ; (delay) ASCII: measure the byte
    li      t5, 0x82
    bne     t9, t5, @@fixed
    addiu   t8, t8, -0x4f       ; (delay) second byte - 0x4f
    sltiu   t8, t8, 0x9b - 0x4f
    beq     t8, zero, @@fixed
    nop
    move    t9, t7              ; full-width: measure the whole code
@@measure:
    addiu   sp, sp, -40
    sw      ra, 16(sp)
    sw      s1, 20(sp)
    sw      s2, 24(sp)
    sw      s3, 28(sp)
    move    s3, t6              ; entry
    jal     PercentForSize      ; a0 = size step
    move    s1, t9              ; (delay) code to measure
    move    s2, v0              ; percent
    move    a0, s1
    jal     WidthFontA
    move    a1, s2
    sltiu   t8, s1, 0x100
    bne     t8, zero, @@done    ; ASCII: no shift
    sw      v0, 32(sp)          ; (delay) width
    jal     GlyphIndex
    move    a0, s1
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
    lhu     t9, 0(s3)
    subu    t9, t9, t8
    sh      t9, 0(s3)
@@done:
    lw      v0, 32(sp)
    addiu   v0, v0, LETTER_SPACING
    lw      s3, 28(sp)
    lw      s2, 24(sp)
    lw      s1, 20(sp)
    lw      ra, 16(sp)
    jr      ra
    addiu   sp, sp, 40
@@fixed:
    j       FixedAdvance
    nop

; a0 = code, a1 = size step, a2 = fixed flag. ASCII units and the half space: ink width
; plus a gap, everything else GlyphAdvance as before. DictAdvance adds 3, which its
; caller turns into ink width + 1 (it subtracts 2); ChoiceAdvance adds the spacing itself.
DictAdvance:
    b       InkAdvance
    li      t7, 3
ChoiceAdvance:
    li      t7, LETTER_SPACING
InkAdvance:
    li      t9, 0x6e87          ; half space: measured like ASCII (8 px at 100%)
    beq     a0, t9, @@measure
    srl     t8, a0, 8
    li      t9, 1
    bne     t8, t9, @@other
    nop
    andi    a0, a0, 0xff        ; ASCII unit: measure the byte, so a space is 8 px
@@measure:
    addiu   sp, sp, -32
    sw      ra, 16(sp)
    sw      a0, 20(sp)
    sw      t7, 24(sp)
    jal     PercentForSize
    move    a0, a1
    lw      a0, 20(sp)
    jal     WidthFontA
    move    a1, v0
    lw      t7, 24(sp)
    addu    v0, v0, t7
    lw      ra, 16(sp)
    jr      ra
    addiu   sp, sp, 32
@@other:
    j       GlyphAdvance
    nop
.endarea

.org 0x088a7b80 + 0x300
.area 1076 - 0x300, 0           ; STRING_HEAP: filled by the build
.endarea

.close
