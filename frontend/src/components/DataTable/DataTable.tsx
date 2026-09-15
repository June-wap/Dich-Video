import React from 'react';
import { EmptyState } from '../EmptyState/EmptyState';

export interface ColumnDef<T> {
  key: string;
  header: string;
  width?: string;
  align?: 'left' | 'center' | 'right';
  render?: (item: T, index: number) => React.ReactNode;
}

export interface DataTableProps<T> {
  columns: ColumnDef<T>[];
  data: T[];
  keyExtractor: (item: T, index: number) => string | number;
  emptyTitle?: string;
  emptyDescription?: string;
  onRowClick?: (item: T) => void;
  className?: string;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  emptyTitle = 'Không tìm thấy dữ liệu',
  emptyDescription = 'Không có bản ghi nào phù hợp với bộ lọc hiện tại.',
  onRowClick,
  className,
}: DataTableProps<T>) {
  if (data.length === 0) {
    return (
      <EmptyState
        title={emptyTitle}
        description={emptyDescription}
      />
    );
  }

  return (
    <div className={`ds-table-wrapper ${className || ''}`}>
      <table className="ds-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className="ds-th"
                style={{
                  width: col.width,
                  textAlign: col.align || 'left',
                }}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((item, rowIdx) => (
            <tr
              key={keyExtractor(item, rowIdx)}
              className="ds-tr"
              onClick={onRowClick ? () => onRowClick(item) : undefined}
              style={{ cursor: onRowClick ? 'pointer' : 'default' }}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className="ds-td"
                  style={{ textAlign: col.align || 'left' }}
                >
                  {col.render
                    ? col.render(item, rowIdx)
                    : (item as Record<string, any>)[col.key] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
