bl_info = {
    "name": "Material Creator from Files",
    "author": "Your Name",
    "version": (1, 1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Material Creator",
    "description": "Create materials from final_vmat_list and valid_png_paths files",
    "warning": "",
    "doc_url": "",
    "category": "Material",
}

import bpy
import os
import math
from bpy.props import StringProperty
from bpy.types import Operator, Panel, PropertyGroup
from bpy_extras.io_utils import ImportHelper


class MaterialCreatorProperties(PropertyGroup):
    """Properties for the Material Creator addon"""
    
    input_file_path: StringProperty(
        name="Material Names File",
        description="Path to the final_vmat_list file containing material names",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )
    
    path_file_path: StringProperty(
        name="Texture Paths File", 
        description="Path to the valid_png_paths file containing texture file paths",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )


class MATERIAL_OT_select_input_file(Operator, ImportHelper):
    """Select the final_vmat_list file containing material names"""
    bl_idname = "material.select_input_file"
    bl_label = "Select Material Names File"
    bl_description = "Select the final_vmat_list file containing material names"
    
    filename_ext = ".txt"
    filter_glob: StringProperty(default="*.txt", options={'HIDDEN'})
    
    def execute(self, context):
        context.scene.material_creator.input_file_path = self.filepath
        return {'FINISHED'}


class MATERIAL_OT_select_path_file(Operator, ImportHelper):
    """Select the valid_png_paths file containing texture paths"""
    bl_idname = "material.select_path_file"
    bl_label = "Select Texture Paths File"
    bl_description = "Select the valid_png_paths file containing texture file paths"
    
    filename_ext = ".txt"
    filter_glob: StringProperty(default="*.txt", options={'HIDDEN'})
    
    def execute(self, context):
        context.scene.material_creator.path_file_path = self.filepath
        return {'FINISHED'}


class MATERIAL_OT_create_materials(Operator):
    """Create materials from the specified files"""
    bl_idname = "material.create_from_files"
    bl_label = "Create Materials"
    bl_description = "Create materials based on the input and path files"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.material_creator
        
        if not props.input_file_path or not props.path_file_path:
            self.report({'ERROR'}, "Please select both input and path files")
            return {'CANCELLED'}
        
        result = self.create_materials_from_files(
            props.input_file_path, 
            props.path_file_path
        )
        
        if result['success']:
            self.report({'INFO'}, f"Successfully created {result['count']} materials and marked as assets")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, result['message'])
            return {'CANCELLED'}
    
    def create_materials_from_files(self, input_file_path, path_file_path):
        """Create materials from the specified files"""
        
        # Read material names from final_vmat_list
        try:
            with open(input_file_path, 'r', encoding='utf-8') as f:
                material_names = [line.strip() for line in f.readlines() if line.strip()]
        except FileNotFoundError:
            return {'success': False, 'message': f"Could not find input file: {input_file_path}"}
        except Exception as e:
            return {'success': False, 'message': f"Error reading input file: {str(e)}"}
        
        # Read texture paths from valid_png_paths
        try:
            with open(path_file_path, 'r', encoding='utf-8') as f:
                texture_paths = []
                for line in f.readlines():
                    line = line.strip()
                    if line:
                        # Remove quotation marks if present
                        line = line.strip('"\'')
                        texture_paths.append(line)
        except FileNotFoundError:
            return {'success': False, 'message': f"Could not find path file: {path_file_path}"}
        except Exception as e:
            return {'success': False, 'message': f"Error reading path file: {str(e)}"}
        
        if not material_names:
            return {'success': False, 'message': "No material names found in input file"}
        
        if not texture_paths:
            return {'success': False, 'message': "No texture paths found in path file"}
        
        # Check if we have the same number of materials and textures
        if len(material_names) != len(texture_paths):
            print(f"Warning: Number of materials ({len(material_names)}) doesn't match number of texture paths ({len(texture_paths)})")
            # Use the minimum of both to avoid index errors
            count = min(len(material_names), len(texture_paths))
            material_names = material_names[:count]
            texture_paths = texture_paths[:count]
        
        created_materials = []
        
        # Create materials
        for i, (mat_name, texture_path) in enumerate(zip(material_names, texture_paths)):
            print(f"Creating material {i+1}/{len(material_names)}: {mat_name}")
            
            # Check if material already exists
            if mat_name in bpy.data.materials:
                print(f"  - Material '{mat_name}' already exists, skipping")
                continue
            
            # Create new material
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            
            # Clear default nodes
            mat.node_tree.nodes.clear()
            
            # Create material output node
            output_node = mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
            output_node.location = (800, 0)
            
            # Create principled BSDF node
            bsdf_node = mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
            bsdf_node.location = (400, 0)
            
            # Connect BSDF to output
            mat.node_tree.links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
            
            # Always create the texture nodes, even if file doesn't exist
            # Create texture coordinate node
            tex_coord_node = mat.node_tree.nodes.new(type='ShaderNodeTexCoord')
            tex_coord_node.location = (-800, 0)
            
            # Create mapping node
            mapping_node = mat.node_tree.nodes.new(type='ShaderNodeMapping')
            mapping_node.location = (-600, 0)
            
            # Create image texture node
            tex_node = mat.node_tree.nodes.new(type='ShaderNodeTexImage')
            tex_node.location = (-400, 0)
            
            # Connect texture coordinate chain
            mat.node_tree.links.new(tex_coord_node.outputs['UV'], mapping_node.inputs['Vector'])
            mat.node_tree.links.new(mapping_node.outputs['Vector'], tex_node.inputs['Vector'])
            
            # Connect Image Texture to Base Color
            mat.node_tree.links.new(tex_node.outputs['Color'], bsdf_node.inputs['Base Color'])
            
            # Always try to load the texture, even if file doesn't exist initially
            try:
                # Normalize the path (handle Windows paths properly)
                normalized_path = os.path.normpath(texture_path)
                
                # Check if image is already loaded to avoid duplicates
                img_name = os.path.basename(normalized_path)
                img = None
                
                # Try to find existing image first by filepath
                for existing_img in bpy.data.images:
                    if existing_img.filepath and os.path.normpath(existing_img.filepath) == normalized_path:
                        img = existing_img
                        print(f"  - Found existing image: {existing_img.name}")
                        break
                
                # If not found, try to load the image
                if img is None:
                    if os.path.exists(normalized_path):
                        img = bpy.data.images.load(normalized_path)
                        print(f"  - Loaded new image: {img.name} from {normalized_path}")
                    else:
                        # Create a placeholder image with the filepath for missing files
                        img = bpy.data.images.new(img_name, 1024, 1024)
                        img.filepath = normalized_path
                        img.source = 'FILE'
                        print(f"  - Created placeholder image: {img.name} with path {normalized_path}")
                        print(f"  - File doesn't exist yet: {normalized_path}")
                
                # Assign image to texture node
                tex_node.image = img
                
                # Set the image filepath explicitly
                img.filepath = normalized_path
                
                # Try to reload the image if it exists
                if os.path.exists(normalized_path):
                    try:
                        img.reload()
                        print(f"  - Image reloaded successfully")
                        print(f"  - Final image size: {img.size[0]}x{img.size[1]}")
                    except:
                        print(f"  - Could not reload image, but filepath is set")
                
                # Set interpolation to Linear for better quality
                tex_node.interpolation = 'Linear'
                
                # Also connect alpha if available
                if 'Alpha' in tex_node.outputs and 'Alpha' in bsdf_node.inputs:
                    mat.node_tree.links.new(tex_node.outputs['Alpha'], bsdf_node.inputs['Alpha'])
                
                print(f"  - Image Texture node filepath set to: {img.filepath}")
                
            except Exception as e:
                print(f"  - Error setting up texture {texture_path}: {e}")
                # Set a fallback color
                bsdf_node.inputs['Base Color'].default_value = (0.8, 0.2, 0.2, 1.0)
                print(f"  - Set red fallback color due to error")
            
            print(f"  - Nodes created: {len(mat.node_tree.nodes)} total")
            print(f"  - Links created: {len(mat.node_tree.links)} total")
            
            created_materials.append(mat)
        
        # Mark all created materials as assets
        for mat in created_materials:
            # Select the material in the outliner/material slots
            bpy.context.view_layer.objects.active = None
            
            # Mark material as asset
            try:
                # Set the material as the active material in the context
                mat.asset_mark()
                print(f"  - Marked '{mat.name}' as asset")
            except Exception as e:
                print(f"  - Could not mark '{mat.name}' as asset: {e}")
                # Alternative method if asset_mark() doesn't work
                try:
                    # Override context for asset operations
                    with bpy.context.temp_override():
                        # Make sure we're in the right context
                        bpy.ops.asset.mark({'material': mat})
                        print(f"  - Marked '{mat.name}' as asset (alternative method)")
                except Exception as e2:
                    print(f"  - Alternative asset marking also failed for '{mat.name}': {e2}")
        
        return {'success': True, 'count': len(created_materials)}


class MATERIAL_OT_create_planes(Operator):
    """Create a plane for each material in the scene"""
    bl_idname = "material.create_planes"
    bl_label = "Create Material Planes"
    bl_description = "Creates a plane for each material and arranges them in a grid"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        result = self.create_material_planes()
        
        if result['success']:
            self.report({'INFO'}, result['message'])
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, result['message'])
            return {'CANCELLED'}
    
    def create_material_planes(self):
        """
        Creates a plane for each material in the scene and arranges them in a grid.
        Each plane will have one material applied to it.
        """
        
        # Get all materials in the scene
        materials = [mat for mat in bpy.data.materials if mat is not None]
        
        if not materials:
            return {'success': False, 'message': "No materials found in the scene!"}
        
        print(f"Found {len(materials)} materials in the scene")
        
        # Clear existing selection
        bpy.ops.object.select_all(action='DESELECT')
        
        # Grid settings
        plane_size = 2.0  # Size of each plane
        spacing = 0.5     # Space between planes
        grid_spacing = plane_size + spacing
        
        # Calculate grid dimensions (roughly square grid)
        grid_width = math.ceil(math.sqrt(len(materials)))
        
        # Create planes for each material
        for i, material in enumerate(materials):
            # Calculate grid position
            row = i // grid_width
            col = i % grid_width
            
            # Calculate world position
            x_pos = col * grid_spacing
            y_pos = row * grid_spacing
            z_pos = 0.0
            
            # Use Blender's default plane mesh which has proper UVs
            bpy.ops.mesh.primitive_plane_add(
                size=plane_size,
                location=(x_pos, y_pos, z_pos)
            )
            
            # Get the newly created object
            obj = bpy.context.active_object
            
            # Rename the object to match the material name
            obj.name = material.name
            obj.data.name = f"Plane_{material.name}"
            
            # Assign material to the object
            if len(obj.data.materials) == 0:
                obj.data.materials.append(material)
            else:
                obj.data.materials[0] = material
            
            print(f"Created plane for material: {material.name} at position ({x_pos:.1f}, {y_pos:.1f}, {z_pos:.1f})")
        
        # Refresh the viewport
        bpy.context.view_layer.update()
        
        message = f"Successfully created {len(materials)} planes arranged in a {grid_width}x{math.ceil(len(materials)/grid_width)} grid"
        print(message)
        return {'success': True, 'message': message}


class MATERIAL_OT_delete_material_planes(Operator):
    """Delete existing material planes"""
    bl_idname = "material.delete_planes"
    bl_label = "Delete Material Planes"
    bl_description = "Delete existing material planes before creating new ones"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        result = self.delete_existing_material_planes()
        
        if result['success']:
            self.report({'INFO'}, result['message'])
            return {'FINISHED'}
        else:
            self.report({'INFO'}, result['message'])
            return {'FINISHED'}
    
    def delete_existing_material_planes(self):
        """
        Delete existing material planes before creating new ones
        """
        # Select all objects that have the same name as materials
        materials = [mat for mat in bpy.data.materials if mat is not None]
        material_planes = [obj for obj in bpy.context.scene.objects if obj.name in [mat.name for mat in materials]]
        
        if material_planes:
            # Select the objects
            bpy.ops.object.select_all(action='DESELECT')
            for obj in material_planes:
                obj.select_set(True)
            
            # Delete selected objects
            bpy.ops.object.delete()
            message = f"Deleted {len(material_planes)} existing material planes"
            print(message)
            return {'success': True, 'message': message}
        else:
            message = "No existing material planes found to delete"
            return {'success': False, 'message': message}
    """Create materials from the specified files"""
    bl_idname = "material.create_from_files"
    bl_label = "Create Materials"
    bl_description = "Create materials based on the input and path files"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        props = context.scene.material_creator
        
        if not props.input_file_path or not props.path_file_path:
            self.report({'ERROR'}, "Please select both input and path files")
            return {'CANCELLED'}
        
        result = self.create_materials_from_files(
            props.input_file_path, 
            props.path_file_path
        )
        
        if result['success']:
            self.report({'INFO'}, f"Successfully created {result['count']} materials and marked as assets")
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, result['message'])
            return {'CANCELLED'}
    
    def create_materials_from_files(self, input_file_path, path_file_path):
        """Create materials from the specified files"""
        
        # Read material names from final_vmat_list
        try:
            with open(input_file_path, 'r', encoding='utf-8') as f:
                material_names = [line.strip() for line in f.readlines() if line.strip()]
        except FileNotFoundError:
            return {'success': False, 'message': f"Could not find input file: {input_file_path}"}
        except Exception as e:
            return {'success': False, 'message': f"Error reading input file: {str(e)}"}
        
        # Read texture paths from valid_png_paths
        try:
            with open(path_file_path, 'r', encoding='utf-8') as f:
                texture_paths = []
                for line in f.readlines():
                    line = line.strip()
                    if line:
                        # Remove quotation marks if present
                        line = line.strip('"\'')
                        texture_paths.append(line)
        except FileNotFoundError:
            return {'success': False, 'message': f"Could not find path file: {path_file_path}"}
        except Exception as e:
            return {'success': False, 'message': f"Error reading path file: {str(e)}"}
        
        if not material_names:
            return {'success': False, 'message': "No material names found in input file"}
        
        if not texture_paths:
            return {'success': False, 'message': "No texture paths found in path file"}
        
        # Check if we have the same number of materials and textures
        if len(material_names) != len(texture_paths):
            print(f"Warning: Number of materials ({len(material_names)}) doesn't match number of texture paths ({len(texture_paths)})")
            # Use the minimum of both to avoid index errors
            count = min(len(material_names), len(texture_paths))
            material_names = material_names[:count]
            texture_paths = texture_paths[:count]
        
        created_materials = []
        
        # Create materials
        for i, (mat_name, texture_path) in enumerate(zip(material_names, texture_paths)):
            print(f"Creating material {i+1}/{len(material_names)}: {mat_name}")
            
            # Check if material already exists
            if mat_name in bpy.data.materials:
                print(f"  - Material '{mat_name}' already exists, skipping")
                continue
            
            # Create new material
            mat = bpy.data.materials.new(name=mat_name)
            mat.use_nodes = True
            
            # Clear default nodes
            mat.node_tree.nodes.clear()
            
            # Create material output node
            output_node = mat.node_tree.nodes.new(type='ShaderNodeOutputMaterial')
            output_node.location = (800, 0)
            
            # Create principled BSDF node
            bsdf_node = mat.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')
            bsdf_node.location = (400, 0)
            
            # Connect BSDF to output
            mat.node_tree.links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])
            
            # Always create the texture nodes, even if file doesn't exist
            # Create texture coordinate node
            tex_coord_node = mat.node_tree.nodes.new(type='ShaderNodeTexCoord')
            tex_coord_node.location = (-800, 0)
            
            # Create mapping node
            mapping_node = mat.node_tree.nodes.new(type='ShaderNodeMapping')
            mapping_node.location = (-600, 0)
            
            # Create image texture node
            tex_node = mat.node_tree.nodes.new(type='ShaderNodeTexImage')
            tex_node.location = (-400, 0)
            
            # Connect texture coordinate chain
            mat.node_tree.links.new(tex_coord_node.outputs['UV'], mapping_node.inputs['Vector'])
            mat.node_tree.links.new(mapping_node.outputs['Vector'], tex_node.inputs['Vector'])
            
            # Connect Image Texture to Base Color
            mat.node_tree.links.new(tex_node.outputs['Color'], bsdf_node.inputs['Base Color'])
            
            # Always try to load the texture, even if file doesn't exist initially
            try:
                # Normalize the path (handle Windows paths properly)
                normalized_path = os.path.normpath(texture_path)
                
                # Check if image is already loaded to avoid duplicates
                img_name = os.path.basename(normalized_path)
                img = None
                
                # Try to find existing image first by filepath
                for existing_img in bpy.data.images:
                    if existing_img.filepath and os.path.normpath(existing_img.filepath) == normalized_path:
                        img = existing_img
                        print(f"  - Found existing image: {existing_img.name}")
                        break
                
                # If not found, try to load the image
                if img is None:
                    if os.path.exists(normalized_path):
                        img = bpy.data.images.load(normalized_path)
                        print(f"  - Loaded new image: {img.name} from {normalized_path}")
                    else:
                        # Create a placeholder image with the filepath for missing files
                        img = bpy.data.images.new(img_name, 1024, 1024)
                        img.filepath = normalized_path
                        img.source = 'FILE'
                        print(f"  - Created placeholder image: {img.name} with path {normalized_path}")
                        print(f"  - File doesn't exist yet: {normalized_path}")
                
                # Assign image to texture node
                tex_node.image = img
                
                # Set the image filepath explicitly
                img.filepath = normalized_path
                
                # Try to reload the image if it exists
                if os.path.exists(normalized_path):
                    try:
                        img.reload()
                        print(f"  - Image reloaded successfully")
                        print(f"  - Final image size: {img.size[0]}x{img.size[1]}")
                    except:
                        print(f"  - Could not reload image, but filepath is set")
                
                # Set interpolation to Linear for better quality
                tex_node.interpolation = 'Linear'
                
                # Also connect alpha if available
                if 'Alpha' in tex_node.outputs and 'Alpha' in bsdf_node.inputs:
                    mat.node_tree.links.new(tex_node.outputs['Alpha'], bsdf_node.inputs['Alpha'])
                
                print(f"  - Image Texture node filepath set to: {img.filepath}")
                
            except Exception as e:
                print(f"  - Error setting up texture {texture_path}: {e}")
                # Set a fallback color
                bsdf_node.inputs['Base Color'].default_value = (0.8, 0.2, 0.2, 1.0)
                print(f"  - Set red fallback color due to error")
            
            print(f"  - Nodes created: {len(mat.node_tree.nodes)} total")
            print(f"  - Links created: {len(mat.node_tree.links)} total")
            
            created_materials.append(mat)
        
        # Mark all created materials as assets
        for mat in created_materials:
            # Select the material in the outliner/material slots
            bpy.context.view_layer.objects.active = None
            
            # Mark material as asset
            try:
                # Set the material as the active material in the context
                mat.asset_mark()
                print(f"  - Marked '{mat.name}' as asset")
            except Exception as e:
                print(f"  - Could not mark '{mat.name}' as asset: {e}")
                # Alternative method if asset_mark() doesn't work
                try:
                    # Override context for asset operations
                    with bpy.context.temp_override():
                        # Make sure we're in the right context
                        bpy.ops.asset.mark({'material': mat})
                        print(f"  - Marked '{mat.name}' as asset (alternative method)")
                except Exception as e2:
                    print(f"  - Alternative asset marking also failed for '{mat.name}': {e2}")
        
        return {'success': True, 'count': len(created_materials)}


class MATERIAL_PT_creator_panel(Panel):
    """Main panel for Material Creator"""
    bl_label = "Material Creator"
    bl_idname = "MATERIAL_PT_creator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Material Creator"
    
    def draw(self, context):
        layout = self.layout
        props = context.scene.material_creator
        
        # File selection section
        box = layout.box()
        box.label(text="File Selection:", icon='FILE_FOLDER')
        
        # Input file selection
        col = box.column(align=True)
        col.label(text="Material Names File (final_vmat_list):")
        row = col.row(align=True)
        row.prop(props, "input_file_path", text="")
        row.operator("material.select_input_file", text="", icon='FILEBROWSER')
        
        # Path file selection
        col.label(text="Texture Paths File (valid_png_paths):")
        row = col.row(align=True)
        row.prop(props, "path_file_path", text="")
        row.operator("material.select_path_file", text="", icon='FILEBROWSER')
        
        # Action section
        layout.separator()
        col = layout.column()
        col.scale_y = 1.5
        
        # Check if files are selected
        if props.input_file_path and props.path_file_path:
            col.operator("material.create_from_files", icon='MATERIAL')
        else:
            col.enabled = False
            col.operator("material.create_from_files", text="Select Files First", icon='ERROR')
        
        # Material Preview section
        layout.separator()
        box = layout.box()
        box.label(text="Material Preview:", icon='MESH_PLANE')
        
        col = box.column(align=True)
        col.operator("material.create_planes", icon='MESH_PLANE')
        col.operator("material.delete_planes", icon='X')
        layout.separator()
        box = layout.box()
        box.label(text="Help:", icon='HELP')
        col = box.column(align=True)
        col.label(text="• final_vmat_list: One material name per line")
        col.label(text="• valid_png_paths: One texture file path per line")
        col.label(text="• Files must have same number of lines")
        col.label(text="• Materials will be automatically marked as assets")


# Registration
classes = [
    MaterialCreatorProperties,
    MATERIAL_OT_select_input_file,
    MATERIAL_OT_select_path_file,
    MATERIAL_OT_create_materials,
    MATERIAL_OT_create_planes,
    MATERIAL_OT_delete_material_planes,
    MATERIAL_PT_creator_panel,
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.material_creator = bpy.props.PointerProperty(type=MaterialCreatorProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.material_creator

if __name__ == "__main__":
    register()