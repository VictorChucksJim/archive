import { FileManager } from "@/components/FileManager";

export default function FolderPage({ params }: { params: { id: string } }) {
  return <FileManager folderId={params.id} />;
}
