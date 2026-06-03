import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { DataFrameEditorModal } from '../components/DataFrameEditorModal';

const sampleMeta = {
  shape: [3, 2] as [number, number],
  columns: ['colA', 'colB'],
  dtypes: { colA: 'int64', colB: 'object' },
  nulls: { colA: 0, colB: 0 },
  rows: [
    { __row_index__: 0, colA: 10, colB: 'hello' },
    { __row_index__: 1, colA: 20, colB: 'world' },
    { __row_index__: 2, colA: 30, colB: 'vitest' },
  ]
};

describe('DataFrameEditorModal', () => {
  it('renders table columns and shape metadata correctly', () => {
    render(
      <DataFrameEditorModal
        label="Test Editor"
        dfMeta={sampleMeta}
        edits={[]}
        onChange={() => {}}
        onClose={() => {}}
      />
    );

    expect(screen.getByText('Test Editor')).toBeInTheDocument();
    expect(screen.getByText('3 rows × 2 cols')).toBeInTheDocument();
    expect(screen.getByText('colA')).toBeInTheDocument();
    expect(screen.getByText('colB')).toBeInTheDocument();
    expect(screen.getByText('hello')).toBeInTheDocument();
    expect(screen.getByText('world')).toBeInTheDocument();
  });

  it('filters rows based on search input', () => {
    render(
      <DataFrameEditorModal
        label="Test Editor"
        dfMeta={sampleMeta}
        edits={[]}
        onChange={() => {}}
        onClose={() => {}}
      />
    );

    const searchInput = screen.getByPlaceholderText('Rechercher dans les données...');
    fireEvent.change(searchInput, { target: { value: 'world' } });

    expect(screen.getByText('world')).toBeInTheDocument();
    expect(screen.queryByText('hello')).not.toBeInTheDocument();
    expect(screen.queryByText('vitest')).not.toBeInTheDocument();
  });

  it('triggers onClose when close button is clicked', () => {
    const handleClose = vi.fn();
    render(
      <DataFrameEditorModal
        label="Test Editor"
        dfMeta={sampleMeta}
        edits={[]}
        onChange={() => {}}
        onClose={handleClose}
      />
    );

    const closeBtn = screen.getByRole('button', { name: 'Fermer' });
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalled();
  });
});
