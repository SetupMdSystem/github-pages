import os
import sys
import glob
import time, struct, os
import random

import bpy, bmesh, mathutils
from bpy.props import *


import nrfile
import nrtools
import nrimp


def isVersionLess280():
    if bpy.app.version < (2, 80, 0):
        return True
    return False


def isVersionGreater280():
    return (not isVersionLess280())


def ver_blender():
    if bpy.app.version < (2, 80, 0):
        return 0
    elif bpy.app.version < (4, 0, 0):
        return 1
    return 2


####??????????????????????
## Shading view
def setFarClipDistance():
    # Set far clip distance
    for a in bpy.context.screen.areas:
        if a.type == 'VIEW_3D':
            for s in a.spaces:
                if s.type == 'VIEW_3D':
                    s.clip_end = 1000000.0


def isImageLoaded(img):
    if not img:
        return False

    if (img.size[0] < 4) and (img.size[1] < 4):
        return False
    return True


class GroupManager(object):
    def __init__(self):
        self.colDict = {}


    def addObjectToCollection(self, groupId0, groupId1, obj):
        if not hasattr(bpy.context.scene, "collection"):
            # Blender < 2.8 has no collections??????
            return None

        parentGroupName = ("grp_{}".format(groupId0))
        parentCollection = self.colDict.get(parentGroupName)
        if not parentCollection:
            #nrtools.logInfo("NewParentGroup={}".format(parentGroupName))
            parentCollection = bpy.data.collections.new(name=parentGroupName)
            bpy.context.scene.collection.children.link(parentCollection)
            self.colDict[parentGroupName] = parentCollection

        childGroupName = ("grp_{}_{}".format(groupId0, groupId1))
        childCollection = self.colDict.get(childGroupName)
        if not childCollection:
            #nrtools.logInfo("NewChildGroup={}".format(childGroupName))
            childCollection = bpy.data.collections.new(name=childGroupName)
            parentCollection.children.link(childCollection) # Add to parent
            self.colDict[childGroupName] = childCollection

        childCollection.objects.link(obj) # Add object to child collection


class MaterialManager(object):    
    def __init__(self):
        self.__matId = 0
        self.__textureCache = {}
        self.loadedImgs = []
        self.failedImgs = []
        self.__materialCache = {}


    def __calcTexListHash(self, texList):
        res = ""
        for texFile in texList:
            res = res + texFile
        return res


    def __createMatName(self):
        matName = "mat_{}".format(self.__matId)
        self.__matId = self.__matId + 1
        return matName


    def __createNewMat(self):
        matName = self.__createMatName()
        mat = bpy.data.materials.new(matName)
        if (False == isVersionLess280()):
            mat.use_nodes = True
        return mat


    # Material == [texFile0+texFile1+texFile2...]
    def __createMaterialCached(self, options, texList):
        #if (0 == len(texList)):
        #    return None

        mat = None
        try:
            texList1 = nrtools.createTexListForTexSlot(options, texList)
            texListHash = self.__calcTexListHash(texList1)
            mat = self.__materialCache.get(texListHash, "materialnotfound")
            if "materialnotfound" == mat:
                # Create new material
                mat = self.__createNewMat()

                if isVersionLess280():
                    # blender <= 2.79
                    self.__createTextures27(mat, options, texList1)
                else:
                    # blender >= 2.8
                    self.__createTextureNodes28(mat, options, texList1, True)

                # Add material to cache.
                # If mat == None then material create error
                self.__materialCache[texListHash] = mat
        except Exception as e:
            nrtools.logError("Exception in __createMaterialCached(): {}".format(str(e)))
            mat = None
        return mat


    def __createMaterial(self, options, texList, vcLayerList):
        mat = None
        try:
            texList1 = nrtools.createTexListForTexSlot(options, texList)
            connectTexImage = (len(vcLayerList) == 0)
            connectVC = not connectTexImage
            mat = self.__createNewMat()
            if isVersionLess280():
                # blender <= 2.79
                if options.isTexCoordEnabled():
                    self.__createTextures27(mat, options, texList1)
            else:
                # blender >= 2.8
                if options.isTexCoordEnabled():
                    self.__createTextureNodes28(mat, options, texList1, connectTexImage)
                if options.isVertexColorEnabled():
                    self.__createVertexColorNodes28(mat, options, vcLayerList, connectVC)
        except Exception as e:
            nrtools.logError("Exception in __createMaterial(): {}".format(str(e)))
            mat = None
        return mat


    # Load textures/Vertex colors
    def createMaterial(self, options, texList, vcLayerList):
        if ((False == options.isTexCoordEnabled() or (0==len(texList))) and (False == options.isVertexColorEnabled())):
            return None

        # If Vertex colors are disabled then use material cache
        if (False == options.isVertexColorEnabled()):
            # Textures only
            return self.__createMaterialCached(options, texList)

        # Textures/Vertex colors
        return self.__createMaterial(options, texList, vcLayerList)


    # Blender >= 2.8
    def __createImage28(self, fullpath):
        # 'None' used as failed to load texture
        img = self.__textureCache.get(fullpath, "notexturefound")
        if "notexturefound" == img:
            img = None
            try:
                img = bpy.data.images.load(fullpath)
                if isImageLoaded(img):
                    nrtools.logInfo("--> SUCCESSFULL load: {}".format(fullpath))
                    self.loadedImgs.append(fullpath)
                else:
                    nrtools.logError("--> FAILED to load: {}".format(fullpath))
                    self.failedImgs.append(fullpath)
                    bpy.data.images.remove(img)
                    img = None
            except Exception as e:
                img = None
            self.__textureCache[fullpath] = img
        return img


    def __createTextureNodes28(self, mat, options, texList, connect):
        if (0 == len(texList)):
            return

        imgObjList = []
        for texFile in texList:
            img = self.__createImage28(texFile)
            imgObjList.append(img)


        bsdf = mat.node_tree.nodes[0] # Assume that first element is 'Principled BSDF'

        idx = 0
        for i, ib in enumerate(imgObjList):
            b = int(str(i/3)[:1])+1
            texImage = mat.node_tree.nodes.new('ShaderNodeTexImage')
            texImage.image = imgObjList[i]
            texImage.location.x -= b*300
            texImage.location.y -= (i-b*3)*300+600
            if (0 == idx) and connect:
                # Assume that bsdf.inputs[0] is  'Base Color'
                # Assume that texImage.outputs[0] is  'Color'
                mat.node_tree.links.new(bsdf.inputs[0], texImage.outputs[0])

            idx = idx + 1
        return


    def __createVertexColorNodes28(self, mat, options, vcLayerList, connect):
        if (0 == len(vcLayerList)):
            return

        bsdf = mat.node_tree.nodes[0]

        vcIdx = 0
        if options.vertCol.vcIdx < len(vcLayerList):
            vcIdx = options.vertCol.vcIdx

        vertColNode = mat.node_tree.nodes.new('ShaderNodeVertexColor')
        vertColNode.layer_name = vcLayerList[vcIdx]
        vertColNode.location.x -= 200
        vertColNode.location.y += 430

        if connect:
            mat.node_tree.links.new(vertColNode.outputs[0], bsdf.inputs[0])


    def __createImageTexture27(self, fullpath):
        tex = self.__textureCache.get(fullpath, "notexturefound")
        if "notexturefound" == tex:
            tex = None
            try:
                img = bpy.data.images.load(fullpath, True)
                if isImageLoaded(img):
                    nrtools.logInfo("--> SUCCESSFULL load: {}".format(fullpath))
                    self.loadedImgs.append(fullpath)
                    # Image loaded successfully
                    #   Create texture
                    tex = bpy.data.textures.new(fullpath, type='IMAGE')
                    tex.image = img
                else:
                    nrtools.logError("--> FAILED to load: {}".format(fullpath))
                    self.failedImgs.append(fullpath)
                    bpy.data.images.remove(img)
                    tex = None
            except Exception as e:
                tex = None
            self.__textureCache[fullpath] = tex
        return tex


    def __createTextures27(self, mat, options, texList):
        if (0 == len(texList)):
            return

        texObjList = []
        for texFile in texList:
            tex = self.__createImageTexture27(texFile)
            texObjList.append(tex)

        i = 0
        slotIdx = 0
        for tex in texObjList:
            if not tex:
                i = i + 1
                continue

            slot = mat.texture_slots.create(slotIdx)
            slot.texture = tex
            if 0 == i:
                slot.use = True
            i = i + 1
            slotIdx = slotIdx + 1
        return


def selectSetObj(obj, flag):
    if not obj:
        return

    if hasattr(obj, "select"):
        obj.select = flag
    elif hasattr(obj, "select_set"):
        obj.select_set(flag)


class BlenderImporter(object):
    def __init__(self):
        self.matMgr = MaterialManager()
        self.totalFilesCount = 0
        self.totalCreated = 0
        self._maxNrSize = 0
        self._maxMeshName = ''
        self.groupMgr = GroupManager()


    def selectLargestObjectViewSelected(self):
        cube = bpy.data.objects.get('Cube')  # Default Cube
        selectSetObj(cube, False)            # Clear selection
        largeObj = bpy.data.objects.get(self._maxMeshName)
        selectSetObj(largeObj, True)
        if isVersionLess280():
            bpy.context.scene.objects.active = largeObj
        else:
            bpy.context.view_layer.objects.active = largeObj


        # Set camera view to active object
        for area in bpy.context.screen.areas:
            if area.type == 'VIEW_3D':
                context_override = bpy.context.copy()
                context_override['area']   = area
                context_override['region'] = area.regions[-1]
                if hasattr(bpy.context, "temp_override"):
                    with bpy.context.temp_override(**context_override):
                        bpy.ops.view3d.view_selected()
                else:
                    bpy.ops.view3d.view_selected(context_override)



    def printInfo(self):
        nrtools.logInfo("Parsed files count={}".format(self.totalFilesCount))
        nrtools.logInfo("Created meshes={}".format(self.totalCreated))
        nrtools.logInfo("Largest NR-file: {}. FileSize={}".format(self._maxMeshName, self._maxNrSize))


    def _createTexCoords(self, options, bm, vatrs, vert, vertexData, texCoordAttrCompIdxList):
        uvList = nrtools.createUVIdxListForUvIdx(options, texCoordAttrCompIdxList)

        for uvIdx in uvList:
            tcAttrComp = texCoordAttrCompIdxList[uvIdx]

            layerTextureCoordinates = nrtools.unpackVertexComponentVaAsList(vert, vertexData, vatrs, [tcAttrComp.u, tcAttrComp.v])
            if None == layerTextureCoordinates:
                continue
            
            if 0 == len(layerTextureCoordinates):
                continue

            if len(layerTextureCoordinates[0]) < 2:
                continue

            # blender 3.5+ ????????????????????????????????????????????????????
            uv_lay = bm.loops.layers.uv.new('uv_' + str(uvIdx))   # BMLayerItem
            for face in bm.faces:
                for vv in face.loops:
                    vertIndex = vv.vert.index
                    uv = mathutils.Vector(layerTextureCoordinates[vertIndex])
                    vv[uv_lay].uv.x = uv.x
                    vv[uv_lay].uv.y = 1.0 - uv.y


    def _createNormals(self, options, mesh, vatrs, vert, vertexData, faces):
        if options.normalVecs.loadMode == nrimp.NormalVectorsLoadMode.Auto:
            autoVAtr = nrtools.createNormalVectorsAuto(vatrs)
            if autoVAtr:
                normals = nrtools.unpackVertexComponentVaAsList(vert, vertexData, vatrs, autoVAtr)
                if not normals:
                    # Use blender AUTOSMOOTH
                    mesh.polygons.foreach_set("use_smooth", [True] * len(faces))
                else:
                    if hasattr(mesh, "use_auto_smooth"):
                        mesh.use_auto_smooth = True
                    mesh.normals_split_custom_set_from_vertices(normals)
            else:
                # NORMAL/NORMALS semantic not found. 
                # Use blender AUTOSMOOTH
                mesh.polygons.foreach_set("use_smooth", [True] * len(faces))

        elif options.normalVecs.loadMode == nrimp.NormalVectorsLoadMode.AttrComp:
            normals = nrtools.unpackVertexComponentVaAsList(vert, vertexData, vatrs, [options.normalVecs.x, options.normalVecs.y, options.normalVecs.z])
            if not normals:
                return

            if hasattr(mesh, "use_auto_smooth"):
                mesh.use_auto_smooth = True
            mesh.normals_split_custom_set_from_vertices(normals)
        return

        
    # Create and load Vertex Colors from vertex data.
    # Return string list with vertex color layer names  [vc_0,vc_1,vc_2....]
    def _createVertexColors(self, options, bm, vatrs, vert, vertexData, vertexColorAttrsIdxList):
        res = []
        idx = 0

        vertCol = options.vertCol
        for colorAttrIdx in vertexColorAttrsIdxList:
            layerName = "vc_{}".format(idx)
        
            color_layer = bm.loops.layers.color.new(layerName)   # 2.79 - 3.5+

            # Detect 3 or 4 component per vertex color (rgb, rgba)
            colorCompsCnt = 4  # blender2.79 -> 3     blender2.8 -> 4
            for face in bm.faces:
                for vv in face.loops:
                    colorCompsCnt = len(vv[color_layer])
                    break
                break

            vertColorsList = nrtools.unpackVertexColorsAsList(vert, vertexData, vatrs, colorAttrIdx, vertCol.r, vertCol.g, vertCol.b, vertCol.a, colorCompsCnt)
            if not vertColorsList:
                continue

            res.append(layerName)
            idx += 1
            for face in bm.faces:
                for vv in face.loops:
                    vertIndex = vv.vert.index
                    vv[color_layer] = vertColorsList[vertIndex]

        return res


    # Create triangle mesh
    def _createMesh(self, options, nrmesh, vatrs, vert, vertexData, positions3, indx, meshName, texList, loadExtraUvData, vatrs1, vert1, vertexData1):
        # Create list of faces
        triangles = indx.read()
        faces = []
        for idx in range(0, int(indx.getIndexCount()/3) ):
            p = struct.unpack_from("iii", triangles, 12*idx)
            faces.append(p)


        #Define mesh and object
        mesh = bpy.data.meshes.new(meshName)
        obj  = bpy.data.objects.new(meshName, mesh)


        #Set location and scene of object
        if hasattr(bpy.context.scene, "cursor_location"):
            obj.location = bpy.context.scene.cursor_location
            bpy.context.scene.objects.link(obj)
        elif hasattr(bpy.context.scene.cursor, "location"):
            obj.location = bpy.context.scene.cursor.location

        # Mesh grouping
        if options.extraOptions.groupMeshes:
            self.groupMgr.addObjectToCollection(nrmesh.getGroup0Id(), nrmesh.getGroup1Id(), obj)
        else:
            if 0 != ver_blender():
                # blender >= 2.80
                bpy.context.collection.objects.link(obj)


        #Create mesh position+indexes
        mesh.from_pydata(positions3, [], faces)


        # Normal vectors
        if options.isNormalVecsEnabled():
            self._createNormals(options, mesh, vatrs, vert, vertexData, faces)


        mesh.update()

        # Switch to bmesh
        bm = bmesh.new()

        try:
            bm.from_mesh(mesh)


            # VertexColors
            vcLayerNamesList = []
            if options.isVertexColorEnabled():
                vertexColorAttrsIdxList = nrtools.createVertexColorAttrsList(vatrs)
                vcLayerNamesList = self._createVertexColors(options, bm, vatrs, vert, vertexData, vertexColorAttrsIdxList)


            mat = self.matMgr.createMaterial(options, texList, vcLayerNamesList)
            if mat:
                obj.data.materials.append(mat)


            bm.verts.ensure_lookup_table()

            # TexCoords
            if options.isTexCoordEnabled():
                if not loadExtraUvData:
                    texCoordAttrList = nrtools.createTexCoordList(options, vatrs)
                    self._createTexCoords(options, bm, vatrs,  vert,  vertexData,  texCoordAttrList)
                else:
                    # Use texcoord from extra UV-data
                    texCoordAttrList = nrtools.createTexCoordList(options, vatrs1)
                    self._createTexCoords(options, bm, vatrs1, vert1, vertexData1, texCoordAttrList)

            bm.to_mesh(mesh)
        finally:
            bm.free()

        # Finalize
        mesh.update()
        return True


    # Create lines
    def _createLines(self, options, nrmesh, vatrs, vert, vertexData, positions3, indx, meshName, texList, loadExtraUvData, vatrs1, vert1, vertexData1):
        # Create list of edges
        lineList = indx.read()
        edges = []
        for idx in range(0, int(indx.getIndexCount()/2) ):
            p = struct.unpack_from("ii", lineList, 8*idx)
            edges.append(p)


        #Define mesh and object
        mesh = bpy.data.meshes.new(meshName)
        obj  = bpy.data.objects.new(meshName, mesh)


        #Set location and scene of object
        if hasattr(bpy.context.scene, "cursor_location"):
            obj.location = bpy.context.scene.cursor_location
            bpy.context.scene.objects.link(obj)
        elif hasattr(bpy.context.scene.cursor, "location"):
            obj.location = bpy.context.scene.cursor.location

        # Mesh grouping
        if options.extraOptions.groupMeshes:
            self.groupMgr.addObjectToCollection(nrmesh.getGroup0Id(), nrmesh.getGroup1Id(), obj)
        else:
            if 0 != ver_blender():
                # blender >= 2.80
                bpy.context.collection.objects.link(obj)


        #Create mesh position+indexes
        mesh.from_pydata(positions3, edges, [])

        mesh.update()

        # Switch to bmesh
        bm = bmesh.new()

        try:
            bm.from_mesh(mesh)


            # VertexColors
            vcLayerNamesList = []
            if options.isVertexColorEnabled():
                vertexColorAttrsIdxList = nrtools.createVertexColorAttrsList(vatrs)
                vcLayerNamesList = self._createVertexColors(options, bm, vatrs, vert, vertexData, vertexColorAttrsIdxList)


            mat = self.matMgr.createMaterial(options, texList, vcLayerNamesList)
            if mat:
                obj.data.materials.append(mat)


            bm.verts.ensure_lookup_table()

            # TexCoords
            if options.isTexCoordEnabled():
                if not loadExtraUvData:
                    texCoordAttrList = nrtools.createTexCoordList(options, vatrs)
                    self._createTexCoords(options, bm, vatrs,  vert,  vertexData,  texCoordAttrList)
                else:
                    # Use texcoord from extra UV-data
                    texCoordAttrList = nrtools.createTexCoordList(options, vatrs1)
                    self._createTexCoords(options, bm, vatrs1, vert1, vertexData1, texCoordAttrList)

            bm.to_mesh(mesh)
        finally:
            bm.free()

        # Finalize
        mesh.update()
        return True


    # Create points
    def _createPoints(self, options, nrmesh, vatrs, vert, vertexData, positions3, meshName):

        #Define mesh and object
        mesh = bpy.data.meshes.new(meshName)
        obj  = bpy.data.objects.new(meshName, mesh)


        #Set location and scene of object
        if hasattr(bpy.context.scene, "cursor_location"):
            obj.location = bpy.context.scene.cursor_location
            bpy.context.scene.objects.link(obj)
        elif hasattr(bpy.context.scene.cursor, "location"):
            obj.location = bpy.context.scene.cursor.location

        # Mesh grouping
        if options.extraOptions.groupMeshes:
            self.groupMgr.addObjectToCollection(nrmesh.getGroup0Id(), nrmesh.getGroup1Id(), obj)
        else:
            if 0 != ver_blender():
                # blender >= 2.80
                bpy.context.collection.objects.link(obj)


        #Create mesh position+indexes
        mesh.from_pydata(positions3, [], [])

        mesh.update()

        # Switch to bmesh
        bm = bmesh.new()

        try:
            bm.from_mesh(mesh)

            # VertexColors
            vcLayerNamesList = []
            if options.isVertexColorEnabled():
                vertexColorAttrsIdxList = nrtools.createVertexColorAttrsList(vatrs)
                vcLayerNamesList = self._createVertexColors(options, bm, vatrs, vert, vertexData, vertexColorAttrsIdxList)

            bm.verts.ensure_lookup_table()

            bm.to_mesh(mesh)
        finally:
            bm.free()

        # Finalize
        mesh.update()
        return True


    def _importTriangleMesh(self, options, nrmesh, vatrs, vert, vertexData, positions3, indx, meshName, texList):
        # Extra vatrs/vertexes
        loadExtraUvData = False
        vert1  = None
        vatrs1 = None
        vertexData1 = None
        if options.texCoord.useExtraUV:
            while (True):
                vert1  = nrmesh.getVertexes(1)
                vatrs1 = nrmesh.getVertexAttributes(1)
                if (not vert1) or (not vatrs1):
                    break

                vertexData1 = vert1.read()
                if not vertexData1:
                    break

                if vert.getVertexCount() != vert1.getVertexCount():
                    nrtools.logError("Vertex count != Extra vertex count {}!={}".format(vert.getVertexCount(), vert1.getVertexCount()))
                    break

                loadExtraUvData = True
                break

        return self._createMesh(options, nrmesh, vatrs, vert, vertexData, positions3, indx, meshName, texList, loadExtraUvData, vatrs1, vert1, vertexData1)


    def _importLineMesh(self, options, nrmesh, vatrs, vert, vertexData, positions3, indx, meshName, texList):
        # Extra vatrs/vertexes
        loadExtraUvData = False
        vert1  = None
        vatrs1 = None
        vertexData1 = None
        if options.texCoord.useExtraUV:
            while (True):
                vert1  = nrmesh.getVertexes(1)
                vatrs1 = nrmesh.getVertexAttributes(1)
                if (not vert1) or (not vatrs1):
                    break

                vertexData1 = vert1.read()
                if not vertexData1:
                    break

                if vert.getVertexCount() != vert1.getVertexCount():
                    nrtools.logError("Vertex count != Extra vertex count {}!={}".format(vert.getVertexCount(), vert1.getVertexCount()))
                    break

                loadExtraUvData = True
                break

        return self._createLines(options, nrmesh, vatrs, vert, vertexData, positions3, indx, meshName, texList, loadExtraUvData, vatrs1, vert1, vertexData1)


    def _importPointMesh(self, options, nrmesh, vatrs, vert, vertexData, positions3, meshName):
        return self._createPoints(options, nrmesh, vatrs, vert, vertexData, positions3, meshName)


    def _importMeshImpl(self, loadPostVs, fileName, options, hashManager):
        nrtools.logInfo("Loading: {}".format(fileName))

        nr = nrfile.NRFile()
        if not nr.parse(fileName):
            nrtools.logError("Ninja Ripper file parsing failed: {}".format(nr.getErrorString()))
            return False

        fileDirectory = os.path.dirname(os.path.abspath(fileName))

        skipPrinted = False
        
        for meshIdx in range(0, nr.getMeshCount()):
            if options.isMeshDubEnabled():
                skip, skipMsg = hashManager.skipMeshLoading(fileName, meshIdx)
                if skip and (not skipPrinted):
                    nrtools.logWarn("{}".format(skipMsg))
                    skipPrinted = True
                    continue

            nrmesh = nr.getMesh(meshIdx)

            # ---Fast checks for mesh stage---
            if loadPostVs:
                if nrfile.ShaderStage.PreVs == nrmesh.getShaderStage():
                    continue
            else:
                if nrfile.ShaderStage.PreVs != nrmesh.getShaderStage():
                    continue


            vatrs = nrmesh.getVertexAttributes(0)
            if None == vatrs:
                nrtools.logError("vertexAttribs == None")
                continue

            if loadPostVs:
                # PostVS attribute with idx==0 is always POSITION with four components (homogeneous coordinates xyzw)
                # TODO: attr_comp x/y/z/w
                if vatrs.getAttr(0).compCount != 4:
                    nrtools.logError("Post vs position not 4 component")
                    continue

            vert = nrmesh.getVertexes(0)
            if not vert:
                nrtools.logError("vertexes == None")
                continue

            vertexData = vert.read()
            if None == vertexData:
                nrtools.logError("vertexData == None")
                continue


            positions3 = None
            if loadPostVs:
                # PostVS
                positions3 = nrtools.createPos3FromPostVsAsList(options, nrmesh, vatrs, vert, vertexData)
            else:
                positions3 = nrtools.createPos3FromPreVsAsList(options, vatrs, vert, vertexData)

            if not positions3:
                nrtools.logError("positions3 == None")
                continue

            meshName = os.path.basename(fileName)
            meshName = os.path.splitext(meshName)[0]
            meshCreated = False
            if nrfile.PrimitiveTopology.TriangleList == nrmesh.getPrimitiveTopology():
                indx = nrmesh.getIndexes(0)
                if not indx:
                    nrtools.logError("indexes == None")
                    continue

                if vert.getVertexCount() < 3:
                    nrtools.logError("TriangleMesh VertexCount < 3")
                    continue

                textures = nrmesh.getTextures()
                texList = nrtools.createTexturesList(textures, fileDirectory)

                # Check texturesCnt == 0
                # Check Quads/Box
                skip, skipMsg = nrtools.isMeshLoadingSkipped(options, vert, indx, textures)
                if skip:
                    nrtools.logWarn("Mesh loading skipped: {}".format(skipMsg))
                    continue

                # Create triangle mesh
                meshCreated = self._importTriangleMesh(options, nrmesh, vatrs, vert, vertexData, positions3, indx, meshName, texList)

            elif nrfile.PrimitiveTopology.LineList == nrmesh.getPrimitiveTopology():
                indx = nrmesh.getIndexes(0)
                if not indx:
                    nrtools.logError("indexes == None")
                    continue

                if vert.getVertexCount() < 2:
                    nrtools.logError("LineMesh VertexCount < 2")
                    continue

                textures = nrmesh.getTextures()
                texList = nrtools.createTexturesList(textures, fileDirectory)

                # Check texturesCnt == 0
                # Check Quads/Box
                skip, skipMsg = nrtools.isMeshLoadingSkipped(options, vert, indx, textures)
                if skip:
                    nrtools.logWarn("LineMesh loading skipped: {}".format(skipMsg))
                    continue

                # Create line mesh
                meshCreated = self._importLineMesh(options, nrmesh, vatrs, vert, vertexData, positions3, indx, meshName, texList)

            elif nrfile.PrimitiveTopology.PointList == nrmesh.getPrimitiveTopology():
                # Create point mesh
                meshCreated = self._importPointMesh(options, nrmesh, vatrs, vert, vertexData, positions3, meshName)

            else:
                nrtools.logError("Import not realized for primitive topology={}".format(nrfile.topologyToStr(nrmesh.getPrimitiveTopology())))

            if meshCreated:
                if nr.getFileSize() > self._maxNrSize:
                    self._maxNrSize = nr.getFileSize()
                    self._maxMeshName = meshName
                self.totalCreated = self.totalCreated + 1

        self.totalFilesCount = self.totalFilesCount + 1
        return True


    def importMesh(self, loadPostVs, fileName, options, hashManager):
        res = False
        #try:
        res = self._importMeshImpl(loadPostVs, fileName, options, hashManager)
        #except Exception as e:
        #    nrtools.logError("_importMeshImpl() Exception: {}".format(str(e)))
        return res


def importFiles(loadPostVs, paths, options):

    hashManager = nrtools.MeshHashesManager()
    hashManager.loadHashes(loadPostVs, paths, options)

    importer = BlenderImporter()

    for file in paths:
        if os.path.isfile(file):
            importer.importMesh(loadPostVs, file, options, hashManager)
        elif os.path.isdir(file):
            fileList = glob.glob(file + "*.nr")
            for file in fileList:
                importer.importMesh(loadPostVs, file, options, hashManager)

    importer.printInfo()
    setFarClipDistance()
    importer.selectLargestObjectViewSelected()
    
