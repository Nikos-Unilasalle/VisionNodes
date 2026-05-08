import React, { memo } from 'react';
import { NodeResizer } from 'reactflow';

export const withNodeResizer = (
  Component: React.ComponentType<any>,
  minWidth: number,
  minHeight: number,
  getColor?: (data: any) => string
) => memo(({ selected, data, ...props }: any) => {
  const color = getColor ? getColor(data) : 'var(--accent, #7c3aed)';
  const isMinified = !!(data as any)?.minified;
  const isCollapsed = !!(data as any)?.params?.collapsed;
  return (
    <div className="w-full" style={{ minWidth: (isMinified || isCollapsed) ? undefined : minWidth, minHeight: (isMinified || isCollapsed) ? undefined : minHeight, height: isMinified ? 22 : '100%', position: 'relative' }}>
      <NodeResizer
        isVisible={selected && !isMinified && !(data as any)?.params?.collapsed}
        minWidth={minWidth}
        minHeight={minHeight}
        color={color}
        handleStyle={{ width: 8, height: 8, borderRadius: 2, zIndex: 20 }}
        lineStyle={{ borderColor: color, borderWidth: 1, opacity: selected ? 0.4 : 0, zIndex: 20 }}
      />
      <Component selected={selected} data={data} {...props} />
    </div>
  );
});
