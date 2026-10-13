# Regenerate with: vhs docs/demo.tape
Output docs/demo.gif
Set FontSize 15
Set Width 1100
Set Height 640
Set Theme "Dracula"
Set TypingSpeed 45ms
Hide
Type `export PATH=$PWD/.venv/bin:$PATH PS1='$ ' && cd $(mktemp -d) && clear` Enter
Show
Type "# a fan controller with a Windows-only app: capture + click labels -> protocol + driver" Enter
Sleep 600ms
Type "usb-rea demo --device fan -o fan" Enter
Sleep 2500ms
Type "sed -n '/^## .fan/,/^Evidence/p' fan/report.md" Enter
Sleep 3500ms
Type `python -c 'import fan.fan_driver as d; print(d.encode(d.FAN, [3100], seq=7).hex(" "))'` Enter
Sleep 3500ms
