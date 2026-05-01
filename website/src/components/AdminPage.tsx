import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { LayoutDashboard, Code, FileJson, Copy, Check, ExternalLink, ShieldCheck } from 'lucide-react';

const AdminPage = () => {
  const [jsonInput, setJsonInput] = useState('');
  const [generatedJson, setGeneratedJson] = useState('');
  const [copied, setCopied] = useState(false);

  // Form states for manual entry or parsing
  const [formData, setFormData] = useState({
    title: '',
    author: '',
    description: '',
    type: 'vn',
    domains: '',
    imageUrl: 'slides/slide1.jpg',
    fileUrl: ''
  });

  const parseFromIssue = () => {
    // Basic parser for the GitHub Issue body format we created
    const lines = jsonInput.split('\n');
    const data: any = { ...formData };
    
    lines.forEach(line => {
      if (line.includes('**Title:**')) data.title = line.split('**Title:**')[1].trim();
      if (line.includes('**Author:**')) data.author = line.split('**Author:**')[1].trim();
      if (line.includes('**File type:**')) data.type = line.includes('.py') ? 'py' : 'vn';
      if (line.includes('**Domains:**')) data.domains = line.split('**Domains:**')[1].trim();
      if (line.includes('**Description:**')) {
        const descIndex = lines.indexOf(line);
        data.description = lines.slice(descIndex + 1, descIndex + 4).join(' ').trim();
      }
    });
    setFormData(data);
  };

  const generate = () => {
    const entry = {
      id: Date.now().toString(),
      type: formData.type,
      title: formData.title,
      author: formData.author,
      description: formData.description,
      domains: formData.domains.split(',').map(d => d.trim()).filter(d => d),
      image: formData.imageUrl,
      fileUrl: formData.fileUrl,
      createdAt: new Date().toISOString().split('T')[0]
    };
    setGeneratedJson(JSON.stringify(entry, null, 2));
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(generatedJson);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="min-h-screen bg-[var(--bg-alt)] pt-24 pb-20">
      <div className="container-md">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-12 h-12 rounded-2xl bg-[var(--accent)] flex items-center justify-center text-white shadow-lg shadow-[var(--accent)]/20">
            <ShieldCheck size={24} />
          </div>
          <div>
            <h1 className="text-[32px] font-bold text-[var(--text-main)]">Admin Dashboard</h1>
            <p className="text-[14px] text-[var(--text-dim)]">Publish community submissions to the gallery</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Step 1: Input from GitHub */}
          <div className="space-y-6">
            <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-3xl p-6 shadow-sm">
              <h2 className="flex items-center gap-2 text-[16px] font-bold text-[var(--text-main)] mb-4">
                <LayoutDashboard size={18} className="text-[var(--accent)]" />
                1. Review Submission
              </h2>
              <p className="text-[13px] text-[var(--text-dim)] mb-4">
                Paste the text from the GitHub Issue body to pre-fill the fields.
              </p>
              <textarea 
                className="vn-input text-[12px] font-mono min-h-[200px] mb-4"
                placeholder="Paste GitHub Issue body here..."
                value={jsonInput}
                onChange={e => setJsonInput(e.target.value)}
              />
              <button onClick={parseFromIssue} className="btn-secondary w-full justify-center">
                Parse Issue Text
              </button>
            </div>

            {/* Step 2: Edit Metadata */}
            <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-3xl p-6 shadow-sm">
              <h2 className="flex items-center gap-2 text-[16px] font-bold text-[var(--text-main)] mb-4">
                <Code size={18} className="text-[var(--accent)]" />
                2. Edit Metadata
              </h2>
              <div className="space-y-4">
                <input 
                  type="text" placeholder="Title" className="vn-input" 
                  value={formData.title} onChange={e => setFormData({...formData, title: e.target.value})}
                />
                <input 
                  type="text" placeholder="Author" className="vn-input" 
                  value={formData.author} onChange={e => setFormData({...formData, author: e.target.value})}
                />
                <textarea 
                  placeholder="Description" className="vn-input min-h-[100px]" 
                  value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})}
                />
                <div className="flex gap-4">
                  <select 
                    className="vn-input flex-1" value={formData.type}
                    onChange={e => setFormData({...formData, type: e.target.value})}
                  >
                    <option value="vn">Pipeline (.vn)</option>
                    <option value="py">Node (.py)</option>
                  </select>
                  <input 
                    type="text" placeholder="Domains (comma separated)" className="vn-input flex-[2]" 
                    value={formData.domains} onChange={e => setFormData({...formData, domains: e.target.value})}
                  />
                </div>
                <input 
                  type="text" placeholder="Image Path (e.g. community/mesh.jpg)" className="vn-input" 
                  value={formData.imageUrl} onChange={e => setFormData({...formData, imageUrl: e.target.value})}
                />
                <input 
                  type="text" placeholder="File URL (Raw GitHub Link)" className="vn-input" 
                  value={formData.fileUrl} onChange={e => setFormData({...formData, fileUrl: e.target.value})}
                />
                <button onClick={generate} className="btn-primary w-full justify-center mt-2">
                  Generate Entry JSON
                </button>
              </div>
            </div>
          </div>

          {/* Step 3: Output */}
          <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-3xl p-6 shadow-sm h-fit sticky top-24">
            <div className="flex items-center justify-between mb-4">
              <h2 className="flex items-center gap-2 text-[16px] font-bold text-[var(--text-main)]">
                <FileJson size={18} className="text-[var(--accent)]" />
                3. Final JSON Entry
              </h2>
              {generatedJson && (
                <button onClick={copyToClipboard} className="text-[var(--accent)] hover:scale-110 transition-transform">
                  {copied ? <Check size={20} /> : <Copy size={20} />}
                </button>
              )}
            </div>
            {generatedJson ? (
              <>
                <pre className="bg-[var(--bg-alt)] border border-[var(--border)] rounded-xl p-4 text-[12px] font-mono overflow-x-auto text-[var(--text-main)] mb-6">
                  {generatedJson}
                </pre>
                <div className="space-y-4">
                  <div className="p-4 rounded-xl bg-blue-500/10 border border-blue-500/20 text-[13px] text-blue-400">
                    <p className="font-bold mb-1">How to publish:</p>
                    <ol className="list-decimal list-inside space-y-1 opacity-80">
                      <li>Copy the JSON snippet above</li>
                      <li>Open <code>website/src/data/community.json</code></li>
                      <li>Paste it into the array</li>
                      <li>Commit and Push to GitHub</li>
                    </ol>
                  </div>
                  <a 
                    href="https://github.com/Nikos-Unilasalle/VisionNodes/edit/main/website/src/data/community.json"
                    target="_blank" rel="noreferrer"
                    className="btn-secondary w-full justify-center gap-2"
                  >
                    <ExternalLink size={14} /> Edit community.json on GitHub
                  </a>
                </div>
              </>
            ) : (
              <div className="py-20 text-center text-[var(--text-xdim)]">
                <FileJson size={48} className="mx-auto mb-4 opacity-20" />
                <p>Fill out the forms to generate the publication data.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default AdminPage;
