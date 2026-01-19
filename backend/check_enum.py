from box_sdk_gen.schemas.folder_mini import FolderMini
from box_sdk_gen.schemas.file_full import FileFull

# Check the enum value
folder_type = FolderMini(id="1", name="test").type
file_type = FileFull(id="1", name="test").type

print(f"Folder type: {folder_type}")
print(f"Folder type as string: {str(folder_type)}")
print(f"Folder type.value: {folder_type.value if hasattr(folder_type, 'value') else 'N/A'}")

print(f"\nFile type: {file_type}")
print(f"File type as string: {str(file_type)}")
print(f"File type.value: {file_type.value if hasattr(file_type, 'value') else 'N/A'}")
