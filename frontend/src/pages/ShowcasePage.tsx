import React, { useState } from 'react';
import {
  Button,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  Input,
  Select,
  TextArea,
  StatusBadge,
  ProgressBar,
  Modal,
} from '../components';
import { useDisclosure } from '../hooks';
import { APP_METADATA } from '../data';

export const ShowcasePage: React.FC = () => {
  const [activeNav, setActiveNav] = useState<'overview' | 'tokens' | 'buttons' | 'forms' | 'feedback' | 'modal'>('overview');
  const modalDisclosure = useDisclosure(false);

  // Form interactive demo states
  const [inputValue, setInputValue] = useState('John Doe');
  const [selectValue, setSelectValue] = useState('vi-VN-Standard-A');
  const [textAreaValue, setTextAreaValue] = useState('Xin chào, đây là bản thử nghiệm tổng hợp tiếng nói cục bộ.');
  const [progressVal, setProgressVal] = useState(65);

  const voiceOptions = [
    { value: 'vi-VN-Standard-A', label: 'Vietnamese (vi-VN) - Nữ Miền Bắc' },
    { value: 'vi-VN-Standard-B', label: 'Vietnamese (vi-VN) - Nam Miền Nam' },
    { value: 'en-US-Jenny', label: 'English (en-US) - Jenny Studio' },
    { value: 'ja-JP-Nanami', label: 'Japanese (ja-JP) - Nanami Neural' },
    { value: 'disabled-opt', label: 'French (fr-FR) - Disabled Option', disabled: true },
  ];

  return (
    <div className="ds-app-layout">
      {/* ------------------------------------------------------------------
          1. DARK NAVY SIDEBAR (Desktop SaaS)
          ------------------------------------------------------------------ */}
      <aside className="ds-sidebar">
        <div className="ds-sidebar-brand">
          <div className="ds-sidebar-brand-icon">V</div>
          <span className="ds-sidebar-brand-text">{APP_METADATA.shortName}</span>
          <span className="ds-sidebar-badge">CP0.3A</span>
        </div>

        <nav className="ds-sidebar-nav">
          <button
            type="button"
            className={`ds-sidebar-item ${activeNav === 'overview' ? 'ds-sidebar-item--active' : ''}`}
            onClick={() => setActiveNav('overview')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7" rx="1"></rect>
              <rect x="14" y="3" width="7" height="7" rx="1"></rect>
              <rect x="14" y="14" width="7" height="7" rx="1"></rect>
              <rect x="3" y="14" width="7" height="7" rx="1"></rect>
            </svg>
            <span>Overview & Grid</span>
          </button>

          <button
            type="button"
            className={`ds-sidebar-item ${activeNav === 'tokens' ? 'ds-sidebar-item--active' : ''}`}
            onClick={() => setActiveNav('tokens')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"></circle>
              <path d="M12 2a10 10 0 0 1 10 10c0 5.523-4.477 10-10 10"></path>
            </svg>
            <span>Design Tokens</span>
          </button>

          <button
            type="button"
            className={`ds-sidebar-item ${activeNav === 'buttons' ? 'ds-sidebar-item--active' : ''}`}
            onClick={() => setActiveNav('buttons')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="6" width="20" height="12" rx="3"></rect>
              <line x1="6" y1="12" x2="18" y2="12"></line>
            </svg>
            <span>Buttons & States</span>
          </button>

          <button
            type="button"
            className={`ds-sidebar-item ${activeNav === 'forms' ? 'ds-sidebar-item--active' : ''}`}
            onClick={() => setActiveNav('forms')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
            <span>Form Inputs & Select</span>
          </button>

          <button
            type="button"
            className={`ds-sidebar-item ${activeNav === 'feedback' ? 'ds-sidebar-item--active' : ''}`}
            onClick={() => setActiveNav('feedback')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
            </svg>
            <span>Badges & Progress</span>
          </button>

          <button
            type="button"
            className={`ds-sidebar-item ${activeNav === 'modal' ? 'ds-sidebar-item--active' : ''}`}
            onClick={() => setActiveNav('modal')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2"></rect>
              <path d="M9 3v18"></path>
            </svg>
            <span>Modal Shell</span>
          </button>
        </nav>

        <div className="ds-sidebar-footer">
          <span>Target: Desktop SaaS</span>
          <StatusBadge status="success" label="Local Core" size="sm" />
        </div>
      </aside>

      {/* ------------------------------------------------------------------
          2. LIGHT WORKSPACE CONTAINER
          ------------------------------------------------------------------ */}
      <div className="ds-workspace-container">
        {/* Topbar */}
        <header className="ds-topbar">
          <div className="ds-topbar-title-group">
            <h1 className="ds-topbar-title">Design System Showcase</h1>
            <span className="ds-topbar-meta">Checkpoint 0.3A-1 Frontend Foundation</span>
          </div>
          <div className="ds-topbar-actions">
            <StatusBadge status="info" label="Resolution Range: 1366x768 to 1920x1080" size="sm" />
            <Button size="sm" variant="outline" onClick={() => modalDisclosure.open()}>
              Open Sample Modal
            </Button>
          </div>
        </header>

        {/* Main Content Area */}
        <main className="ds-main-content">
          <div className="ds-content-container">

            {/* Banner info */}
            <Card>
              <CardContent style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px' }}>
                <div>
                  <h2 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                    Frontend Design Foundation & Component Verification
                  </h2>
                  <p style={{ fontSize: '13px', color: 'var(--neutral-500)', marginTop: '2px' }}>
                    Dark navy sidebar, light workspace, blue primary accent, slate neutrals, 8–12px radius, and standard component states.
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <StatusBadge status="success" label="React 19" size="sm" />
                  <StatusBadge status="success" label="TypeScript" size="sm" />
                  <StatusBadge status="success" label="Vite" size="sm" />
                </div>
              </CardContent>
            </Card>

            {/* ------------------------------------------------------------------
                SECTION 1: DESIGN TOKENS
                ------------------------------------------------------------------ */}
            <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                1. Global Design Tokens
              </h2>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
                {/* Dark Navy Sidebar Tokens */}
                <Card>
                  <CardHeader>
                    <CardTitle>Dark Navy Sidebar Palette</CardTitle>
                    <CardDescription>High contrast desktop sidebar tokens</CardDescription>
                  </CardHeader>
                  <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', background: 'var(--sidebar-bg)', color: '#fff', borderRadius: 'var(--radius-md)' }}>
                      <span>Sidebar BG (#0b1329)</span>
                      <code>--sidebar-bg</code>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', background: 'var(--sidebar-bg-hover)', color: '#fff', borderRadius: 'var(--radius-md)' }}>
                      <span>Sidebar Hover (#17254a)</span>
                      <code>--sidebar-bg-hover</code>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', background: 'var(--sidebar-bg-active)', color: '#fff', borderRadius: 'var(--radius-md)' }}>
                      <span>Sidebar Active (#1d305f)</span>
                      <code>--sidebar-bg-active</code>
                    </div>
                  </CardContent>
                </Card>

                {/* Primary Accent Tokens */}
                <Card>
                  <CardHeader>
                    <CardTitle>Primary Accent (Blue)</CardTitle>
                    <CardDescription>Action triggers and focal states</CardDescription>
                  </CardHeader>
                  <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', background: 'var(--color-primary-600)', color: '#fff', borderRadius: 'var(--radius-md)' }}>
                      <span>Primary Accent (#2563eb)</span>
                      <code>--color-primary-600</code>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', background: 'var(--color-primary-700)', color: '#fff', borderRadius: 'var(--radius-md)' }}>
                      <span>Primary Hover (#1d4ed8)</span>
                      <code>--color-primary-700</code>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', background: 'var(--color-primary-50)', color: 'var(--color-primary-800)', border: '1px solid var(--color-primary-200)', borderRadius: 'var(--radius-md)' }}>
                      <span>Subtle Tint (#eff6ff)</span>
                      <code>--color-primary-50</code>
                    </div>
                  </CardContent>
                </Card>

                {/* Neutrals & Radii */}
                <Card>
                  <CardHeader>
                    <CardTitle>Radius & Neutrals</CardTitle>
                    <CardDescription>Standard 8–12px radius and borders</CardDescription>
                  </CardHeader>
                  <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', background: 'var(--neutral-100)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}>
                      <span>Border Default (#e2e8f0)</span>
                      <span>Radius MD: 8px</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', background: 'var(--neutral-200)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-lg)' }}>
                      <span>Border Strong (#cbd5e1)</span>
                      <span>Radius LG: 10px</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', background: 'var(--surface-white)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-xl)', boxShadow: 'var(--shadow-xs)' }}>
                      <span>Surface White (#ffffff)</span>
                      <span>Radius XL: 12px</span>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </section>

            {/* ------------------------------------------------------------------
                SECTION 2: BUTTON COMPONENT & STATES
                ------------------------------------------------------------------ */}
            <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                2. Button Component (Variants, Sizes & States)
              </h2>

              <Card>
                <CardHeader>
                  <CardTitle>Button Variants</CardTitle>
                  <CardDescription>Primary, Secondary, Outline, Ghost, Danger</CardDescription>
                </CardHeader>
                <CardContent>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
                    <Button variant="primary">Primary Action</Button>
                    <Button variant="secondary">Secondary Action</Button>
                    <Button variant="outline">Outline Action</Button>
                    <Button variant="ghost">Ghost Action</Button>
                    <Button variant="danger">Danger Action</Button>
                  </div>
                </CardContent>
              </Card>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '16px' }}>
                {/* Button Sizes */}
                <Card>
                  <CardHeader>
                    <CardTitle>Button Sizes</CardTitle>
                    <CardDescription>Small (28px), Medium (36px), Large (42px)</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <Button size="sm">Small (28px)</Button>
                      <Button size="md">Medium (36px)</Button>
                      <Button size="lg">Large (42px)</Button>
                    </div>
                  </CardContent>
                </Card>

                {/* Button States */}
                <Card>
                  <CardHeader>
                    <CardTitle>Component States</CardTitle>
                    <CardDescription>Default, Disabled, Loading, Error</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', alignItems: 'center' }}>
                      <Button variant="primary">Default</Button>
                      <Button variant="primary" disabled>Disabled</Button>
                      <Button variant="primary" isLoading loadingText="Generating...">Loading</Button>
                      <Button variant="primary" isError>Error State</Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </section>

            {/* ------------------------------------------------------------------
                SECTION 3: FORM CONTROLS (Input, Select, TextArea)
                ------------------------------------------------------------------ */}
            <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                3. Form Controls (Input, Select, TextArea) & States
              </h2>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
                {/* Inputs */}
                <Card>
                  <CardHeader>
                    <CardTitle>Input Component States</CardTitle>
                    <CardDescription>Default, Focus, Disabled, Loading, Error</CardDescription>
                  </CardHeader>
                  <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <Input
                      label="Speaker / Profile Name"
                      placeholder="e.g. Mai Thao (vi-VN)"
                      value={inputValue}
                      onChange={(e) => setInputValue(e.target.value)}
                      hint="Enter speaker display name."
                    />

                    <Input
                      label="Input with Left Icon"
                      placeholder="Search voices or models..."
                      leftIcon={
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <circle cx="11" cy="11" r="8"></circle>
                          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                        </svg>
                      }
                    />

                    <Input
                      label="Loading State"
                      defaultValue="Resolving provider artifacts..."
                      isLoading
                      hint="Network or disk inspection active."
                    />

                    <Input
                      label="Disabled Input"
                      defaultValue="Read-only system model parameter"
                      disabled
                      hint="Locked by system configuration."
                    />

                    <Input
                      label="Error State Input"
                      defaultValue="invalid-format-path*"
                      error="Illegal characters in path: asterisk (*) is not allowed."
                    />
                  </CardContent>
                </Card>

                {/* Select & TextArea */}
                <Card>
                  <CardHeader>
                    <CardTitle>Select & TextArea Controls</CardTitle>
                    <CardDescription>Dropdown selection and multi-line text input</CardDescription>
                  </CardHeader>
                  <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <Select
                      label="Selected Voice Profile"
                      options={voiceOptions}
                      value={selectValue}
                      onChange={(e) => setSelectValue(e.target.value)}
                      hint="Choose local TTS voice checkpoint."
                    />

                    <Select
                      label="Disabled Select"
                      disabled
                      options={voiceOptions}
                      value="vi-VN-Standard-A"
                      hint="Provider unavailable."
                    />

                    <TextArea
                      label="Source Script / Text"
                      value={textAreaValue}
                      onChange={(e) => setTextAreaValue(e.target.value)}
                      rows={3}
                      hint="Plain text input for chunking and inference."
                    />

                    <TextArea
                      label="TextArea with Error State"
                      defaultValue="Script text exceeded quota limit..."
                      error="Text length exceeds 5,000 characters for a single chunk."
                      rows={2}
                    />
                  </CardContent>
                </Card>
              </div>
            </section>

            {/* ------------------------------------------------------------------
                SECTION 4: STATUS BADGES & PROGRESS BARS
                ------------------------------------------------------------------ */}
            <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                4. Feedback Elements (StatusBadge & ProgressBar)
              </h2>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
                {/* Badges */}
                <Card>
                  <CardHeader>
                    <CardTitle>StatusBadges</CardTitle>
                    <CardDescription>Semantic status indicators (dot + label)</CardDescription>
                  </CardHeader>
                  <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
                      <StatusBadge status="success" label="Installed / Ready" />
                      <StatusBadge status="warning" label="Downloading (45%)" />
                      <StatusBadge status="error" label="Failed / Corrupted" />
                      <StatusBadge status="info" label="Processing Job" />
                      <StatusBadge status="neutral" label="Not Installed" />
                    </div>

                    <div style={{ marginTop: '8px' }}>
                      <p style={{ fontSize: '12px', color: 'var(--neutral-500)', marginBottom: '8px' }}>Small Size:</p>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
                        <StatusBadge size="sm" status="success" label="Active" />
                        <StatusBadge size="sm" status="warning" label="Queued" />
                        <StatusBadge size="sm" status="error" label="Cancelled" />
                        <StatusBadge size="sm" status="info" label="Syncing" />
                        <StatusBadge size="sm" status="neutral" label="Idle" />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Progress Bars */}
                <Card>
                  <CardHeader>
                    <CardTitle>Progress Bars</CardTitle>
                    <CardDescription>Determinate, indeterminate, and state variants</CardDescription>
                  </CardHeader>
                  <CardContent style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    <ProgressBar
                      label="Model Artifact Download"
                      value={progressVal}
                      showPercent
                      size="md"
                    />

                    <div style={{ display: 'flex', gap: '8px' }}>
                      <Button size="sm" variant="outline" onClick={() => setProgressVal((p) => Math.max(0, p - 15))}>
                        -15%
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => setProgressVal((p) => Math.min(100, p + 15))}>
                        +15%
                      </Button>
                    </div>

                    <ProgressBar
                      label="TTS Synthesis Chunks Complete"
                      value={100}
                      showPercent
                      status="success"
                      size="sm"
                    />

                    <ProgressBar
                      label="Indeterminate Task (Local Engine Warmup)"
                      indeterminate
                      size="sm"
                    />

                    <ProgressBar
                      label="Failed Batch Generation"
                      value={42}
                      showPercent
                      status="error"
                      size="sm"
                    />
                  </CardContent>
                </Card>
              </div>
            </section>

            {/* ------------------------------------------------------------------
                SECTION 5: CARDS & CONTAINERS
                ------------------------------------------------------------------ */}
            <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                5. Card Shell & Structured Containers
              </h2>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
                <Card interactive>
                  <CardHeader>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <CardTitle>TTS Provider</CardTitle>
                      <StatusBadge status="success" label="Active Provider" size="sm" />
                    </div>
                    <CardDescription>Primary local inference provider</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <p style={{ fontSize: '13px', color: 'var(--neutral-600)', lineHeight: '1.5' }}>
                      Card with interactive hover elevation, structured header, metadata badge, and action footer.
                    </p>
                  </CardContent>
                  <CardFooter>
                    <Button size="sm" variant="ghost">Details</Button>
                    <Button size="sm" variant="primary">Configure</Button>
                  </CardFooter>
                </Card>

                <Card>
                  <CardHeader>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <CardTitle>Persistence Storage</CardTitle>
                      <StatusBadge status="neutral" label="SQLite 3" size="sm" />
                    </div>
                    <CardDescription>Durable job and voice state storage</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <p style={{ fontSize: '13px', color: 'var(--neutral-600)', lineHeight: '1.5' }}>
                      Ensures jobs, chunks, profiles, and models persist across restarts with ACID integrity.
                    </p>
                  </CardContent>
                  <CardFooter>
                    <Button size="sm" variant="outline">Inspect DB</Button>
                  </CardFooter>
                </Card>
              </div>
            </section>

            {/* ------------------------------------------------------------------
                SECTION 6: MODAL SHELL VERIFICATION
                ------------------------------------------------------------------ */}
            <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                6. Modal Shell Component
              </h2>

              <Card>
                <CardContent style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--neutral-900)' }}>
                      Interactive Modal Shell Verification
                    </h3>
                    <p style={{ fontSize: '13px', color: 'var(--neutral-500)' }}>
                      Test modal backdrop, Escape key listener, title header, scrollable body, and action footer.
                    </p>
                  </div>
                  <Button variant="primary" onClick={() => modalDisclosure.open()}>
                    Launch Modal Shell
                  </Button>
                </CardContent>
              </Card>
            </section>

          </div>
        </main>
      </div>

      {/* ------------------------------------------------------------------
          MODAL INSTANCE
          ------------------------------------------------------------------ */}
      <Modal
        isOpen={modalDisclosure.isOpen}
        onClose={() => modalDisclosure.close()}
        title="Create Voice Profile"
        description="Configure a new localized voice profile preset for TTS generation."
        size="md"
        footer={
          <>
            <Button variant="ghost" onClick={() => modalDisclosure.close()}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => modalDisclosure.close()}>
              Save Voice Profile
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <Input
            label="Profile Name"
            placeholder="e.g. Vietnamese Female Northern Accent"
            defaultValue="Vietnamese Northern Accent Standard"
            required
          />

          <Select
            label="Target Language"
            options={[
              { value: 'vi', label: 'Vietnamese (Tiếng Việt)' },
              { value: 'en', label: 'English' },
              { value: 'zh', label: 'Chinese (中文)' },
              { value: 'ja', label: 'Japanese (日本語)' },
            ]}
            defaultValue="vi"
          />

          <TextArea
            label="Profile Description & Notes"
            placeholder="Add context notes regarding voice pitch, pacing or target use-case..."
            rows={3}
          />

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', background: 'var(--neutral-50)', border: '1px solid var(--border-default)', borderRadius: 'var(--radius-md)' }}>
            <span style={{ fontSize: '13px', color: 'var(--neutral-700)' }}>Offline Status Verification</span>
            <StatusBadge status="success" label="Local Core Valid" size="sm" />
          </div>
        </div>
      </Modal>
    </div>
  );
};
