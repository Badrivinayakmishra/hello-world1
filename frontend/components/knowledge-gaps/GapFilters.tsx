import React from 'react'

interface GapFiltersProps {
  searchQuery: string
  onSearchChange: (query: string) => void
  selectedCategory: string
  onCategoryChange: (category: string) => void
  selectedPriority: string
  onPriorityChange: (priority: string) => void
  sortBy: string
  onSortChange: (sort: string) => void
  categories: { [key: string]: number }
  priorities: { [key: string]: number }
}

export default function GapFilters({
  searchQuery,
  onSearchChange,
  selectedCategory,
  onCategoryChange,
  selectedPriority,
  onPriorityChange,
  sortBy,
  onSortChange,
  categories,
  priorities
}: GapFiltersProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 mb-4">
      {/* Search */}
      <div className="flex-1 min-w-[200px]">
        <input
          type="text"
          placeholder="Search gaps..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:border-gray-500"
          style={{
            fontFamily: '"Work Sans", sans-serif'
          }}
        />
      </div>

      {/* Category Filter */}
      <select
        value={selectedCategory}
        onChange={(e) => onCategoryChange(e.target.value)}
        className="px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:border-gray-500 bg-white"
        style={{
          fontFamily: '"Work Sans", sans-serif',
          color: '#081028'
        }}
      >
        <option value="">All Categories</option>
        {Object.entries(categories).map(([cat, count]) => (
          <option key={cat} value={cat}>
            {cat} ({count})
          </option>
        ))}
      </select>

      {/* Priority Filter */}
      <select
        value={selectedPriority}
        onChange={(e) => onPriorityChange(e.target.value)}
        className="px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:border-gray-500 bg-white"
        style={{
          fontFamily: '"Work Sans", sans-serif',
          color: '#081028'
        }}
      >
        <option value="">All Priorities</option>
        {Object.entries(priorities).map(([pri, count]) => (
          <option key={pri} value={pri}>
            {pri} ({count})
          </option>
        ))}
      </select>

      {/* Sort */}
      <select
        value={sortBy}
        onChange={(e) => onSortChange(e.target.value)}
        className="px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:border-gray-500 bg-white"
        style={{
          fontFamily: '"Work Sans", sans-serif',
          color: '#081028'
        }}
      >
        <option value="default">Default Order</option>
        <option value="priority">Priority (High First)</option>
        <option value="unanswered">Unanswered First</option>
        <option value="newest">Newest First</option>
        <option value="quality">Highest Quality</option>
      </select>
    </div>
  )
}
