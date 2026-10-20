
#!/bin/bash

# Infinite loop: open blank TextEdit documents
while true; do
    open -a TextEdit
    osascript -e 'tell application "TextEdit" to make new document'
    sleep 1
done
