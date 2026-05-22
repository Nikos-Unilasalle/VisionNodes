import React from 'react';
import { Bold, Italic, Code, List, Link, Strikethrough } from 'lucide-react';

export function insertMarkdown(
  textarea: HTMLTextAreaElement | null,
  prefix: string,
  suffix: string = '',
  onChange: (val: string) => void
) {
  if (!textarea) return;
  const start = textarea.selectionStart;
  const end = textarea.selectionEnd;
  const text = textarea.value;
  
  const selectedText = text.substring(start, end);
  const newText = text.substring(0, start) + prefix + selectedText + suffix + text.substring(end);
  
  onChange(newText);
  
  // Restore focus and cursor position after React re-renders
  setTimeout(() => {
    textarea.focus();
    textarea.setSelectionRange(start + prefix.length, end + prefix.length);
  }, 0);
}

export const MarkdownToolbar = ({ 
  textareaRef, 
  value, 
  onChange,
  className = ''
}: { 
  textareaRef: React.RefObject<HTMLTextAreaElement>,
  value: string,
  onChange: (val: string) => void,
  className?: string
}) => {
  return (
    <div className={`flex gap-1 p-1 bg-black/20 border-b border-black/10 flex-wrap ${className}`}>
      <button type="button" onMouseDown={(e) => { e.preventDefault(); insertMarkdown(textareaRef.current, '**', '**', onChange); }} className="p-1 hover:bg-white/10 rounded text-gray-500 hover:text-white transition-colors" title="Bold"><Bold size={12} /></button>
      <button type="button" onMouseDown={(e) => { e.preventDefault(); insertMarkdown(textareaRef.current, '*', '*', onChange); }} className="p-1 hover:bg-white/10 rounded text-gray-500 hover:text-white transition-colors" title="Italic"><Italic size={12} /></button>
      <button type="button" onMouseDown={(e) => { e.preventDefault(); insertMarkdown(textareaRef.current, '~~', '~~', onChange); }} className="p-1 hover:bg-white/10 rounded text-gray-500 hover:text-white transition-colors" title="Strikethrough"><Strikethrough size={12} /></button>
      <div className="w-px h-3 bg-white/10 self-center mx-0.5" />
      <button type="button" onMouseDown={(e) => { e.preventDefault(); insertMarkdown(textareaRef.current, '`', '`', onChange); }} className="p-1 hover:bg-white/10 rounded text-gray-500 hover:text-white transition-colors" title="Code"><Code size={12} /></button>
      <button type="button" onMouseDown={(e) => { e.preventDefault(); insertMarkdown(textareaRef.current, '\n- ', '', onChange); }} className="p-1 hover:bg-white/10 rounded text-gray-500 hover:text-white transition-colors" title="List"><List size={12} /></button>
      <button type="button" onMouseDown={(e) => { e.preventDefault(); insertMarkdown(textareaRef.current, '[', '](url)', onChange); }} className="p-1 hover:bg-white/10 rounded text-gray-500 hover:text-white transition-colors" title="Link"><Link size={12} /></button>
    </div>
  );
};
