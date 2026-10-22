// TODO: Sprint 1 - Resume Tags + Rename UI: add the editor and mutation controls.
import { useState } from "react";
import type { Resume } from "../../types";

type ResumeTagsRenameProps = {
  resume: Resume;
  onSave: (updatedResume: Resume) => void;
};

export function ResumeTagsRename({
  resume,
  onSave,
}: ResumeTagsRenameProps) {

  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(resume.name);
  const [tags, setTags] = useState<string[]>(resume.tags);
  const [newTag, setNewTag] = useState("");

function saveChanges() {
  if (!name.trim()) return; 

  onSave({
    ...resume, 
    name: name.trim(),
    tags: tags, 
  }); 

  setEditing(false); 
}

function cancelChanges() {
  setName(resume.name); 
  setTags([...resume.tags]); 
  setNewTag(""); 
  setEditing(false); 
}

function addTag() {
  const tag = newTag.trim();

  if (
    tag &&
    !tags.some(
      (existingTag) =>
        existingTag.toLowerCase() === tag.toLowerCase()
    )
  ) {
    setTags([...tags, tag]);
  }

  setNewTag("");
}

function removeTag(tagToRemove: string) {
  setTags(tags.filter((tag) => tag !== tagToRemove)); 

}
  return (
  <div className="resume-metadata-editor">
    <h3 className="resume-title">{resume.name}</h3>

    {!editing ? (
      <div>
        {resume.tags.map((tag) => (
        <span className="resume-tag" key={tag}>
        {tag}
        </span>
        ))}

        <button className="button button-secondary"
          type="button"
          onClick={() => {
            setName(resume.name);
            setTags([...resume.tags]);
            setNewTag("");
            setEditing(true);
          }}
        >
          Rename / Edit Tags
        </button>
      </div>
    ) : (
      <div>
        <label className="resume-input" htmlFor="resume-name">Resume Name:</label>
        <input
          id="resume-name"
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />

        <h4>Tags</h4>

        {tags.map((tag) => (
          <span className="resume-tag" key={tag}>
            {tag}
            <button
              className="resume-tag-remove"
              type="button"
              onClick={() => removeTag(tag)}
              aria-label={`Remove ${tag}`}
            >
              X
            </button>
          </span>
        ))}
        <div className="resume-tag-input-row">
          <input 
            type="text"
            placeholder="Enter a tag"
            value={newTag}
            onChange={(e) => setNewTag(e.target.value)}
          />

          <button type="button" onClick={addTag}>
            Add Tag
          </button>
        </div>
        
        <div className="resume-actions">
          <button
              type="button"
              onClick={saveChanges}
              disabled={!name.trim()}
            >
              Save
          </button>

          <button type="button" onClick={cancelChanges}>
            Cancel
          </button>
        </div>
      </div>
    )}
  </div>
);
}