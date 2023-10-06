import fontforge
import os

FONT_VARSION = '1.0'

if __name__ == '__main__':
    font = fontforge.open('config.sfd')
    font.version = FONT_VARSION
    font.selection.all()
    font.clear()
    font.createChar(32).width = 512 #空格

    count = 0
    fileList = os.listdir('glyphs')
    total = len(fileList)
    for filename in fileList:
        count += 1
        char = filename[0]
        code = ord(char)

        print("(%d/%d)%s: import symbol glyph '%s' %d from %s" % (count, total, font.fontname, char, code, filename))
        glyph = font.createChar(code)
        glyph.importOutlines('glyphs/' +filename)

    font.generate(font.fontname + ".ttf")
    font.close()
