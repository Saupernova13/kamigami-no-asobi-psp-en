Kamigami no Asobi English Patch v1.0
====================================

An English translation patch for Kamigami no Asobi (PSP, Japan,
NPJH50809). It changes the script, menus, quiz, dictionary, Mythology Monologue,
chapter titles and the text drawn into the game's images.

The patch contains no game data. You need your own copy of the Japanese UMD as
an ISO image.

Original ISO (check before patching):
  size    1,445,789,696 bytes
  SHA-256 DED26F15C287D26D91EFBDB1BA78D1B5CA46939636A5711750ED2007803AFE16

Applying the patch
------------------
Windows:   put the original ISO in this folder and drag it onto
           apply-patch.bat. The English ISO is written next to it.
           (Or use any xdelta UI: "Delta Patcher", "xdelta UI".)
Linux, macOS, Steam Deck:
           sh apply-patch.sh /path/to/original.iso
           (needs xdelta3: apt install xdelta3 / brew install xdelta)
By hand:   xdelta3 -d -s original.iso Kamigami-no-Asobi-EN-v1.0.xdelta "Kamigami no Asobi - English v1.0.iso"

The result must have SHA-256
  61492C95D99D3DA3321C5E6B4B1C59DCB423960C892991690DBD7CCAF9161115

Playing
-------
PPSSPP (PC, Android, Steam Deck) or a PSP with custom firmware. On a PSP, put
the ISO in ISO/ on the memory stick.

The player's default name is Yui. Name entry opens on its alphabet page; the
L and R buttons switch to the kana pages.

Notes
-----
- Most of the story text is machine-translated and has not been edited by
  hand yet. Menus, names, titles and image text were translated by hand.
- The fixed family name (Kusanagi) is left blank in the name box: its
  3-character slot cannot hold it, and the story never inserts it.
- Built from commit af9748d on 2026-10-06.

Credits
-------
Translation tooling, engine patch and translation: Saupernova13.
Built with armips (Kingcom), pspdecrypt (John-K), PPSSPP (testing) and
xdelta3 (Joshua MacDonald). Kamigami no Asobi (c) Broccoli. This is an
unofficial fan translation; please support the official release.
