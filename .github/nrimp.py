
import os
import sys
import struct


class TexcoordLoadMode:
    Disabled = 0
    Auto     = 1  # uAttrIdx/uCompIdx and vAttrIdx/vCompIdx  calculated in importMesh()
    AttrName = 2  # TEXCOORD + uComp + vComp
    AttrComp = 3  # uAttrComp + vAttrComp


class NormalVectorsLoadMode:
    Disabled = 0
    Auto     = 1 # attrIdx/compIdx calculated in importMesh()
    AttrComp = 2


class VertexColorsLoadMode:
    Disabled = 0
    Auto     = 1 # attrIdx/compIdx calculated in importMesh()


class MeshDuplicateLoadMode:
    Disabled = 0
    Auto     = 1 #  idx+tag, idx+tag, idx+tag...


# Attrib index[0-63]/Component index[0-3]
class AttrComp(object):
    def __init__(self, attr, comp):
        self.attr = attr
        self.comp = comp

    def __str__(self):
        return 'attr={} comp={}'.format(self.attr, self.comp)


class TexCoordAttrComp(object):
    def __init__(self, uAttrComp, vAttrComp):
        self.u = uAttrComp # AttrComp(1, 0)
        self.v = vAttrComp # AttrComp(1, 1)




class PositionLoadMode:
    Auto     = 0    # Attribute calculated in importMesh()
    AttrComp = 1


class PositionTransformMode:
    Matrix = 0
    FOV    = 1    # Matrix calculated in importMesh() fov+width/height from .nr
    OrthoProj = 2 # Orthographic projection. Matrix calculated in importMesh() width/height from .nr


def PositionLoadModeToStr(e):
    if PositionLoadMode.Auto == e:
        return "Auto"
    elif PositionLoadMode.AttrComp == e:
        return "AttrComp"
    return "Unknown"


def TexcoordLoadModeToStr(e):
    if TexcoordLoadMode.Auto == e:
        return "Auto"
    elif TexcoordLoadMode.AttrName == e:
        return "AttrName"
    elif TexcoordLoadMode.AttrComp == e:
        return "AttrComp"
    elif TexcoordLoadMode.Disabled == e:
        return "Disabled"
    return "Unknown"


def PositionTransformModeToStr(e):
    if PositionTransformMode.Matrix == e:
        return "Matrix"
    elif PositionTransformMode.FOV == e:
        return "FOV"
    elif PositionTransformMode.OrthoProj == e:
        return "OrthoProj"
    return "Unknown"


def NormalVectorsLoadModeToStr(e):
    if NormalVectorsLoadMode.Disabled == e:
        return "Disabled"
    elif NormalVectorsLoadMode.Auto == e:
        return "Auto"
    elif NormalVectorsLoadMode.AttrComp == e:
        return "AttrComp"
    return "Unknown"


def VertexColorsLoadModeToStr(e):
    if VertexColorsLoadMode.Disabled == e:
        return "Disabled"
    elif VertexColorsLoadMode.Auto == e:
        return "Auto"
    return "Unknown"


def MeshDuplicateLoadModeToStr(e):
    if MeshDuplicateLoadMode.Disabled == e:
        return "Disabled"
    elif MeshDuplicateLoadMode.Auto == e:
        return "Auto"
    return "Unknown"


class PosPreVs(object):
    def __init__(self):
        self.loadMode = PositionLoadMode.Auto
        self.x = AttrComp(0, 0) # X/Y/Z-ATTR/COMP
        self.y = AttrComp(0, 1)
        self.z = AttrComp(0, 2)

    def __str__(self):
        baseStr = "loadMode={}".format(PositionLoadModeToStr(self.loadMode))
        if PositionLoadMode.Auto == self.loadMode:
            return baseStr
        elif PositionLoadMode.AttrComp == self.loadMode:
            return "{} x=[{}] y=[{}] z=[{}]".format(baseStr, self.x, self.y, self.z)
        return "Unknown"


class PosPostVs(object):
    def __init__(self):
        self.loadMode = PositionLoadMode.Auto
        self.transformMode = PositionTransformMode.FOV
        self.projMat = [[1.8106601717798212, 0.0, 0.0, 0.0], [0.0, 2.414213562373095, 0.0, 0.0], [0.0, 0.0, 1.000010000100001, 1.0], [0.0, 0.0, -0.01000010000100001, 0.0]]
        self.fovY = 45.0               # Perspective Projection
        self.useRightHanded = False
        #self.useMatFovRH = False
        # TODO: PostVS component selection
        self.x = AttrComp(0, 0) # X/Y/Z-ATTR/COMP
        self.y = AttrComp(0, 1)
        self.z = AttrComp(0, 2)
        self.w = AttrComp(0, 3)

    def __str__(self):
        baseStr = "loadMode={} transformMode={}".format(PositionLoadModeToStr(self.loadMode), PositionTransformModeToStr(self.transformMode))
        if PositionTransformMode.Matrix == self.transformMode:
            return "{} projMat: {}".format(baseStr, str(self.projMat))
        elif PositionTransformMode.FOV == self.transformMode:
            return "{} fovY={} useRightHanded={}".format(baseStr, self.fovY, self.useRightHanded)
        elif PositionTransformMode.OrthoProj == self.transformMode:
            return "{} useRightHanded={}".format(baseStr, self.useRightHanded)
        return "Unknown"


class TexCoords(object):
    def __init__(self):
        self.loadMode = TexcoordLoadMode.Auto
        self.useExtraUV = False  # World--> Local   Local-->World
        self.textureSlotIdx = 0  # Default texture slot index used as 'Diffuse'
        #   ATTRNAME/ATTR_COMP
        self.uvIdx     = 0 # Default UV Map index in multiple UV-case
        self.attrName  = 'TEXCOORD'
        self.uAttrComp = AttrComp(1, 0)
        self.vAttrComp = AttrComp(1, 1)

    def __str__(self):
        baseStr = "loadMode={}".format(TexcoordLoadModeToStr(self.loadMode))
        baseStr2 = "useExtraUV={} texSlot={}".format(self.useExtraUV, self.textureSlotIdx)

        if (TexcoordLoadMode.Auto == self.loadMode):
            return "{} {}".format(baseStr, baseStr2)
        elif (TexcoordLoadMode.Disabled == self.loadMode):
            return "{}".format(baseStr)
        elif TexcoordLoadMode.AttrName == self.loadMode:
            return "{} {} attrib={} uComp={} vComp={} uvIdx={}".format(baseStr, baseStr2, self.attrName, self.uAttrComp.comp, self.vAttrComp.comp, self.uvIdx)
        elif TexcoordLoadMode.AttrComp == self.loadMode:
            return "{} {} u=[{}] v=[{}]".format(baseStr, baseStr2, self.uAttrComp, self.vAttrComp)
        return "Unknown"


class NormalVectors(object):
    def __init__(self):
        self.loadMode = NormalVectorsLoadMode.Auto
        self.x = AttrComp(2, 0)  # X/Y/Z-ATTR/COMP
        self.y = AttrComp(2, 1)
        self.z = AttrComp(2, 2)

    def __str__(self):
        baseStr = "loadMode={}".format(NormalVectorsLoadModeToStr(self.loadMode))
        if (NormalVectorsLoadMode.Auto == self.loadMode) or (NormalVectorsLoadMode.Disabled == self.loadMode):
            return baseStr
        elif NormalVectorsLoadMode.AttrComp == self.loadMode:
            return "{} x=[{}] y=[{}] z=[{}]".format(baseStr, self.x, self.y, self.z)
        return "Unknown"


class VertexColors(object):
    def __init__(self):
        self.loadMode = VertexColorsLoadMode.Disabled
        self.vcIdx = 0
        self.r = 0 # R/G/B/A-Indexes [0-3]
        self.g = 1
        self.b = 2
        self.a = 3

    def __str__(self):
        baseStr = "loadMode={}".format(VertexColorsLoadModeToStr(self.loadMode))
        if (VertexColorsLoadMode.Disabled == self.loadMode):
            return baseStr
        return "{} vcIdx={} r={} g={} b={} a={}".format(baseStr, self.vcIdx, self.r, self.g, self.b, self.a)


class ExtraOptions(object):
    def __init__(self):
        self.groupMeshes = False
        self.dontLoadMeshesWithoutTextures = False
        self.dontLoadQuadMeshes = False
        self.dontLoadBoxMeshes = False

    def __str__(self):
        return "groupMeshes={} dontLoadMeshesWithoutTextures={} dontLoadQuadMeshes={} dontLoadBoxMeshes={}".format(self.groupMeshes, self.dontLoadMeshesWithoutTextures, self.dontLoadQuadMeshes, self.dontLoadBoxMeshes)


class MeshDuplicateTag(object):
    def __init__(self, idx, tag):
        self.idx = idx  # Mesh=0/ExtraMesh=1
        self.tag = tag

    def __str__(self):
        return 'idx={} tag={}'.format(self.idx, self.tag)


class MeshDuplicate(object):
    def __init__(self):
        self.loadMode = MeshDuplicateLoadMode.Disabled
        self.hashTags = []  # [MeshDuplicateTag, MeshDuplicateTag, MeshDuplicateTag,....]

    def addTag(self, idx, tag):
        self.hashTags.append(MeshDuplicateTag(idx, tag))

    def __str__(self):
        baseStr = "loadMode={}".format(MeshDuplicateLoadModeToStr(self.loadMode))
        if MeshDuplicateLoadMode.Disabled == self.loadMode:
            return "{}".format(baseStr)

        s = ""
        for x in self.hashTags:
            s = s + "[{}]".format(str(x))
        return "{} hashTagOptions=[{}]".format(baseStr, s)


class ImportOptions(object):
    def __init__(self):
        self.posPostVs    = PosPostVs()
        self.posPreVs     = PosPreVs()
        self.texCoord     = TexCoords()
        self.normalVecs   = NormalVectors()
        self.vertCol      = VertexColors()
        self.extraOptions = ExtraOptions()
        self.meshDup      = MeshDuplicate()


    def isNormalVecsEnabled(self):
        return self.normalVecs.loadMode != NormalVectorsLoadMode.Disabled

    def isTexCoordEnabled(self):
        return self.texCoord.loadMode != TexcoordLoadMode.Disabled

    def isVertexColorEnabled(self):
        return self.vertCol.loadMode != VertexColorsLoadMode.Disabled

    def isMeshDubEnabled(self):
        return self.meshDup.loadMode != MeshDuplicateLoadMode.Disabled

    def dump(self, postVs):
        if postVs:
            print("PosPostVs=[{}]".format(self.posPostVs))
        else:
            print("PosPreVs=[{}]".format(self.posPreVs))

        print("TexCoord=[{}]".format(self.texCoord))
        print("NormalVecs=[{}]".format(self.normalVecs))
        print("VertexColors=[{}]".format(self.vertCol))
        print("ExtraOptions=[{}]".format(self.extraOptions))
        print("MeshDup=[{}]".format(self.meshDup))

