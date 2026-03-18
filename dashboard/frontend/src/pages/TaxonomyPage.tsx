import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { TaxonomyNode } from '../api/client'

function TreeNode({ node, depth = 0 }: { node: TaxonomyNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 1)
  const hasChildren = node.children.length > 0

  return (
    <div>
      <div
        className="flex items-center gap-2 py-1 hover:bg-card-hover rounded transition-colors"
        style={{ paddingLeft: `${depth * 20 + 8}px` }}
      >
        {hasChildren ? (
          <button
            onClick={() => setExpanded(!expanded)}
            className="w-4 h-4 flex items-center justify-center text-text-muted hover:text-text-secondary"
          >
            <svg className={`w-3 h-3 transition-transform ${expanded ? 'rotate-90' : ''}`} fill="currentColor" viewBox="0 0 20 20">
              <path d="M6 4l8 6-8 6V4z" />
            </svg>
          </button>
        ) : (
          <span className="w-4 h-4 flex items-center justify-center text-text-muted">-</span>
        )}
        <Link
          to={`/themes/${encodeURIComponent(node.name)}`}
          className="text-sm text-accent hover:text-accent-hover"
        >
          {node.name}
        </Link>
        {node.stock_count > 0 && (
          <span className="text-xs text-text-muted">({node.stock_count})</span>
        )}
      </div>
      {expanded && hasChildren && (
        <div>
          {node.children.map((child) => (
            <TreeNode key={child.name} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function TaxonomyPage() {
  const [tree, setTree] = useState<TaxonomyNode[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.taxonomy().then(setTree).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-12 text-text-muted">Loading...</div>

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-text-primary">Theme Taxonomy</h1>
      <p className="text-sm text-text-muted">
        {tree.length} root families. Click to explore themes. Promote open themes via the Promotions page.
      </p>
      <div className="bg-card rounded-lg border border-border p-4">
        {tree.map((node) => (
          <TreeNode key={node.name} node={node} />
        ))}
      </div>
    </div>
  )
}
