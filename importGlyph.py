import sys
import os
import json
import math
import copy

sys.path.append('clsvg')
from clsvg import svgfile
from clsvg import bezierShape

GLYPH_ATTRIB = {
    'version': '1.1',
    'x': '0',
    'y': '0',
    'viewBox': '0 0 1024 1024',
    'style': 'enable-background:new 0 0 1024 1024;',
    'xmlns': "http://www.w3.org/2000/svg",
    'space': 'preserve'
    }
TEMP_GLYPH_FILE = 'tempGlyph.svg'
FONT_SIZE = 1024
STROKE_WIDTH = 64
GLYPFH_WIDTH = 0.8
FONT_VARSION = "1.0"

def loadJson(file):
    with open(file, 'r', encoding='utf-8') as f:
        return json.load(f)
    
def lineSymbol(p1, p2):
    if p1.x == p2.x:
        return 'v'
    elif p1.y == p2.y:
        return 'h'
    else:
        return 'd'
    
def getCharData(data, scale=1):
    p_map = {'h': set(), 'v': set()}
    path_list = []
    collision = {}
    for list in data['comb']["key_paths"]:
        prep = None
        path = []

        isHide = False
        for kp in list['points']:
            if kp['p_type'] == "Hide":
                isHide = True
                break
        if isHide: continue

        for kp in list['points']:
            pos = bezierShape.Point(kp['point'][0] * scale, kp['point'][1] * scale)
            if pos != prep:
                p_map['h'].add(pos.x)
                p_map['v'].add(pos.y)
                path.append(pos)
                prep = pos
        
        if len(path) > 1:
            head = { "symbol": lineSymbol(path[0], path[1]), "index": len(path_list)}
            tail = { "symbol": lineSymbol(path[-1], path[-2]), "index": len(path_list)}
            if path[0] != path[-1]:
                if path[0] in collision:
                    collision[path[0]].append(head)
                else:
                    collision[path[0]] = [head]

                if path[-1] in collision:
                    collision[path[-1]].append(tail)
                else:
                    collision[path[-1]] = [tail]

            path_list.append(path)

    map_to = {}
    for p, infos in collision.items():
        infos.sort(key=lambda x: x['symbol'], reverse=False)
        def mapToIndex(i):
            while i in map_to:
                i = map_to[i]
            return i
        while len(infos) > 1:
            oneInfo = infos.pop()
            towInfo = infos.pop()
            oneIndex = mapToIndex(oneInfo['index'])
            towIndex = mapToIndex(towInfo['index'])

            if oneIndex != towIndex:
                map_to[towIndex] = oneIndex
                if path_list[oneIndex][0] == p:
                    path_list[oneIndex].reverse()
                if path_list[towIndex][0] != p:
                    path_list[towIndex].reverse()
                path_list[oneIndex] +=  path_list[towIndex][1:]

    bpaths = []
    for i, points in enumerate(path_list):
        if i not in map_to:
            bp = bezierShape.BezierPath()
            bp.start(points[0])
            bp.extend([bezierShape.BezierCtrl(points[j] - points[j-1]) for j in range(1, len(points))])
            if points[0] == points[-1]:
                bp.close()
            bpaths.append(bp)

    scale = data["info"]["scale"]
    p_map['h'] = sorted(p_map['h'])
    p_map['v'] = sorted(p_map['v'])

    return scale, p_map, bpaths

def getStrucView(bpaths, p_map):
    def x(v):
        return p_map['h'].index(v)
    def y(v):
        return p_map['v'].index(v)

    view = [[[] for n in range(len(p_map['h']))] for m in range(len(p_map['v']))]

    for i, path in enumerate(bpaths):
        start = path.startPos()
        prePos = bezierShape.Point(x(start.x), y(start.y))
        for j, ctrl in enumerate(path):
            sym = lineSymbol(bezierShape.Point(), ctrl.pos)
            attrs = {
                'symbol': sym,
                'indexes': [i, j],
                'padding': False
            }
            view[prePos.y][prePos.x].append(attrs)
            start += ctrl.pos
            currPos = bezierShape.Point(x(start.x), y(start.y))
            view[currPos.y][currPos.x].append(attrs)

            if sym != 'd':
                attrs = {
                    'symbol': sym,
                    'indexes': [i, j],
                    'padding': True
                }
                if sym == 'h':
                    for k in range(min(prePos.x, currPos.x) + 1, max(prePos.x, currPos.x)):
                        view[currPos.y][k].append(attrs)
                if sym == 'v':
                    for k in range(min(prePos.y, currPos.y) + 1, max(prePos.y, currPos.y)):
                        view[k][currPos.x].append(attrs)

            prePos = currPos

    return view

def toOutline(bpath, strokeWidth, p_map, view, scale):
    def x(v):
        return p_map['h'].index(v)
    
    def y(v):
        return p_map['v'].index(v)
    
    def extendedType(pos, tangent):
        viewX = x(pos.x)
        viewY = y(pos.y)

        for attrs in view[viewY][viewX]:
            if attrs['padding']:
                return "Non"
        
        if tangent.x == 0:
            if tangent.y < 0:
                if viewY == 0:
                    return "All"
                else:
                    check_list = []
                    advance = viewY
                    while advance != 0:
                        advance -= 1
                        if p_map['v'][viewY] - p_map['v'][advance] < STROKE_WIDTH * 3 / 2:
                            check_list.append(advance)
                        else:
                            break

                    for check in check_list:
                        for attrs in view[check][viewX]:
                            if attrs['symbol'] != 'd':
                                if p_map['v'][viewY] - p_map['v'][check] < STROKE_WIDTH:
                                    return "Non"
                                else:
                                    return "Half"
                    return "All"
            else:
                if viewY + 1 == len(p_map['v']):
                    return 'All'
                else:
                    check_list = []
                    advance = viewY
                    while advance + 1 != len(p_map['v']):
                        advance += 1
                        if p_map['v'][advance] - p_map['v'][viewY] < STROKE_WIDTH * 3 / 2:
                            check_list.append(advance)
                        else:
                            break

                    for check in check_list:
                        for attrs in view[check][viewX]:
                            if attrs['symbol'] != 'd':
                                if p_map['v'][viewY] - p_map['v'][check] < STROKE_WIDTH:
                                    return "Non"
                                else:
                                    return "Half"
                    return "All"
                
        if tangent.y == 0:
            if tangent.x < 0:
                if viewX == 0:
                    return "All"
                else:
                    check_list = []
                    advance = viewX
                    while advance != 0:
                        advance -= 1
                        if p_map['h'][viewX] - p_map['h'][advance] < STROKE_WIDTH * 3 / 2:
                            check_list.append(advance)
                        else:
                            break

                    for check in check_list:
                        for attrs in view[viewY][check]:
                            if attrs['symbol'] != 'd':
                                if p_map['h'][viewX] - p_map['h'][check] < STROKE_WIDTH:
                                    return "Non"
                                else:
                                    return "Half"
                    return "All"
            else:
                if viewX + 1 == len(p_map['h']):
                    return 'All'
                else:
                    check_list = []
                    advance = viewX
                    while advance + 1 != len(p_map['h']):
                        advance += 1
                        if p_map['h'][advance] - p_map['h'][viewX] < STROKE_WIDTH * 3 / 2:
                            check_list.append(advance)
                        else:
                            break

                    for check in check_list:
                        for attrs in view[viewY][check]:
                            if attrs['symbol'] != 'd':
                                if p_map['h'][viewX] - p_map['h'][check] < STROKE_WIDTH:
                                    return "Non"
                                else:
                                    return "Half"
                    return "All"
                
        return 'Non'

    def join(path1, path2, ctrl1, ctrl2, en, sn):
        if sn == None:
            path1.append(ctrl1)
            path2.append(ctrl2)
        else:
            radian = en.rotate(-sn.radian()).radian()
            if radian > 0:
                joinProcess(path1, path2, ctrl1, ctrl2, en, sn, radian)
            elif radian < 0:
                joinProcess(path2, path1, ctrl2, ctrl1, -en, -sn, -radian)
            else:
                path1.append(ctrl1)
                path2.append(ctrl2)

    def joinProcess(path1, path2, ctrl1, ctrl2, en, sn, radian):
        ePos = en - sn
        if radian - 0.001 < math.pi / 2:
            etangent = -en.perpendicular()
            stangent = sn.perpendicular()
            intersection = bezierShape.intersection(bezierShape.Point(), stangent, ePos, ePos + etangent)

            path1.connect(intersection)
            path1.connect(ePos - intersection)
        else:
            path1.connect(ePos)
        path1.append(ctrl1)
        
        aPos = path2.endPos()
        bPos = aPos
        connectPos = aPos + sn - en
        plist = copy.deepcopy(path2._ctrlList)
        while 1:
            bPos = bPos - plist[-1].pos
            iList1, iList2 = plist[-1].intersections(bPos, ctrl2, connectPos)
            if len(iList1):                    
                plist[-1] = plist[-1].splitting(max(iList1))[0]
                plist.append(ctrl2.splitting(min(iList2))[1])
                path2._ctrlList = plist
                break
            elif len(plist) > 1:
                plist.pop()
            else:
                raise Exception('Join failed!')
                break
    
    radius = strokeWidth / 2
    newPath = [bezierShape.BezierPath(),  bezierShape.BezierPath()]
    prePos = bpath.startPos()
    preNormals = None

    for ctrl in bpath:
        # if ctrl.pos.isOrigin():
        #     continue
        normals = ctrl.pos.normalization(radius).perpendicular()
        currPos = prePos + ctrl.pos

        if preNormals == None:
            preNormals = normals
            newPath[0].start(prePos + preNormals)
            newPath[1].start(prePos - preNormals)

        join(newPath[0], newPath[1], ctrl, ctrl, normals, preNormals)

        prePos = currPos
        preNormals = normals

    if bpath.isClose():
        tailCtrl = []
        for path in newPath:
            tailCtrl.append(path[0])
            path.setStartPos(path.startPos() + path[0].pos)
            path.popFront()

        normals,_ = bpath[0].normals(0, radius)
        join(newPath[0], newPath[1], tailCtrl[0], tailCtrl[1], normals, preNormals)
        
        newPath[0].close()
        newPath[1].close()
        newPath[1] = newPath[1].reverse()
    else:
        path = newPath[1].reverse()
        p2 = path.startPos()
        endPos = newPath[0].endPos()

        stangent = -preNormals.perpendicular()
        etype = extendedType(currPos, stangent)
        if etype != "Non":
            if etype == "Half":
                stangent /= 2
            newPath[0].connect(stangent)
            newPath[0].connect(p2 - endPos)
            newPath[0].connect(-stangent)
            newPath[0].connectPath(path)
        else:
            newPath[0].connect(p2 - endPos)
            newPath[0].connectPath(path)

        stangent = newPath[0][-1].pos.normalization(radius)
        etype = extendedType(bpath.startPos(), stangent)
        if etype != 'Non':
            if etype == "Half":
                stangent /= 2
            newPath[0].connect(stangent)
            newPath[0].connect(newPath[0].startPos() - newPath[1].startPos())

        path = newPath[0]
        path.close()
        newPath = [path]

    return newPath

def writeTempGlyphFromShapes(shapes, fileName, tag, attrib):
    newRoot = svgfile.ET.Element(tag, attrib)
    newRoot.text = '\n'
    styleElem = svgfile.ET.Element('style', { 'type': 'text/css' })
    styleElem.text = '.st0{fill:#000000;}'
    styleElem.tail = '\n'
    newRoot.append(styleElem)

    for shape in shapes:
        newRoot.append(shape.toSvgElement({ 'class': 'st0' }))
    newTree = svgfile.ET.ElementTree(newRoot)
    newTree.write(fileName, encoding = "utf-8", xml_declaration = True)

def testChar(char):
    data = loadJson('./comb_data/comb_data.json')
    scale, p_map, bpaths = getCharData(data[char], FONT_SIZE)
    view = getStrucView(bpaths, p_map)

    shapes = []
    for bpath in bpaths:
        shape = bezierShape.BezierShape()
        shape.extend(toOutline(bpath, STROKE_WIDTH, p_map, view, scale))
        shape.transform(move=bezierShape.Point(FONT_SIZE * (1-GLYPFH_WIDTH) / 2))
        shapes.append(shape)

    writeTempGlyphFromShapes(shapes, TEMP_GLYPH_FILE, 'svg', GLYPH_ATTRIB)

def corrections(list):
    import fontforge
    font = fontforge.open("YuFanZhenSu.sfd")

    num = len(list)
    count = 0
    data = loadJson('./comb_data/comb_data.json')
    for name in list:
        attrs = data[name]

        char = name
        code = ord(char)
        if code < 128:
            width = int(FONT_SIZE / 2)
        else:
            width = FONT_SIZE
        
        scale, p_map, bpaths = getCharData(attrs, FONT_SIZE)
        view = getStrucView(bpaths, p_map)
        shapes = []
        for bpath in bpaths:
            shape = bezierShape.BezierShape()
            shape.extend(toOutline(bpath, STROKE_WIDTH, p_map, view, scale))
            shape.transform(move=bezierShape.Point(FONT_SIZE * (1-GLYPFH_WIDTH) / 2))
            shapes.append(shape)
            
        writeTempGlyphFromShapes(shapes, TEMP_GLYPH_FILE, 'svg', GLYPH_ATTRIB)
        glyph = font.createChar(code)
        glyph.clear()
        glyph.importOutlines(TEMP_GLYPH_FILE)
        glyph.width = width
        glyph.removeOverlap()
        
        count += 1
        print("(%d/%d)%s: import glyph '%s' %d" % (count, num, font.fontname, char, code))            
    
    font.generate(font.fontname + ".otf")
    font.save(font.fontname + ".sfd")
    font.close()

    os.remove(TEMP_GLYPH_FILE)

def importGlyphs():
    import fontforge
    font = fontforge.open("config.sfd")
    font.version = FONT_VARSION
    font.createChar(32).width = int(FONT_SIZE/2) #空格

    data = loadJson('./comb_data/comb_data.json')
    errorList = {}
    num = len(data)
    count = 0
    
    for name, attrs in data.items():
        char = name
        code = ord(char)
        if code < 128:
            width = int(FONT_SIZE / 2)
        else:
            width = FONT_SIZE
        
        count += 1
        print("(%d/%d)%s: import glyph '%s' %d" % (count, num, font.fontname, char, code))
        
        scale, p_map, bpaths = getCharData(attrs, FONT_SIZE)
        view = getStrucView(bpaths, p_map)
        shapes = []
        try:
            for bpath in bpaths:
                shape = bezierShape.BezierShape()
                shape.extend(toOutline(bpath, STROKE_WIDTH, p_map, view, scale))
                shape.transform(move=bezierShape.Point(FONT_SIZE * (1-GLYPFH_WIDTH) / 2))
                shapes.append(shape)
        except Exception as e:
            errorList[char] = e
            print(char, e)
        
        writeTempGlyphFromShapes(shapes, TEMP_GLYPH_FILE, 'svg', GLYPH_ATTRIB)
        glyph = font.createChar(code)
        glyph.importOutlines(TEMP_GLYPH_FILE)
        glyph.width = width
        
    if len(errorList):
        print("\n%d glyphs with errors!" % len(errorList))
        for name, e in errorList.items():
            print(name, e)

    font.selection.all()
    font.removeOverlap()
    
    print("\n%s: The Font has %d glyphs" % (font.fontname, count - len(errorList)))
    print("Generate font file in %s\n" % (font.fontname + ".otf"))
    
    font.generate(font.fontname + ".otf")
    font.save(font.fontname + ".sfd")
    font.close()

    os.remove(TEMP_GLYPH_FILE)

if __name__ == '__main__':
    importGlyphs()