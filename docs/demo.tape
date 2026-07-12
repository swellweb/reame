# vhs script for the README demo GIF.
#   brew install vhs
#   vhs docs/demo.tape        (run from the repo root; needs the qwen2.5-1.5b
#                              model already in ~/.reame/models)
Output docs/figures/demo.gif

Set FontSize 16
Set Width 920
Set Height 480
Set Padding 12
Set TypingSpeed 35ms

Hide
Type "export PATH=$PWD/build/src:$PATH && clear"
Enter
Sleep 500ms
Show

Type "reame list"
Sleep 500ms
Enter
Sleep 3.5s

Type `reame run qwen2.5-1.5b "Explain mmap in one sentence."`
Sleep 500ms
Enter
Sleep 9s
