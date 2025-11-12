import React, { useState } from 'react';
import './SearchBar.css';

function SearchBar({ onSearch, onFilterChange }) {
  const [query, setQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    cuisineTypes: [],
    priceRange: '',
    atmosphere: '',
    dietaryRestrictions: [],
  });

  const handleSearch = () => {
    if (query.trim()) {
      const preferences = {
        cuisine_types: filters.cuisineTypes,
        price_range: filters.priceRange || null,
        atmosphere: filters.atmosphere || null,
        dietary_restrictions: filters.dietaryRestrictions,
      };
      onSearch(query, preferences);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const handleFilterChange = (filterName, value) => {
    const newFilters = { ...filters, [filterName]: value };
    setFilters(newFilters);
    if (onFilterChange) {
      onFilterChange(newFilters);
    }
  };

  const toggleCuisineType = (cuisine) => {
    const newCuisines = filters.cuisineTypes.includes(cuisine)
      ? filters.cuisineTypes.filter((c) => c !== cuisine)
      : [...filters.cuisineTypes, cuisine];
    handleFilterChange('cuisineTypes', newCuisines);
  };

  const cuisineOptions = ['한식', '중식', '일식', '양식', '카페', '디저트', '아시안'];
  const priceOptions = ['저렴', '보통', '비싼편', '고급'];
  const atmosphereOptions = ['캐주얼', '데이트', '비즈니스', '가족 모임'];

  return (
    <div className="search-bar-container">
      <div className="search-input-wrapper">
        <input
          type="text"
          className="search-input"
          placeholder="맛집을 검색해보세요... (예: 강남 파스타, 분위기 좋은 이탈리안)"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={handleKeyPress}
        />
        <button className="search-button" onClick={handleSearch}>
          검색
        </button>
        <button
          className="filter-toggle-button"
          onClick={() => setShowFilters(!showFilters)}
        >
          {showFilters ? '필터 닫기' : '필터 열기'}
        </button>
      </div>

      {showFilters && (
        <div className="filters-panel">
          <div className="filter-section">
            <h4>음식 종류</h4>
            <div className="filter-chips">
              {cuisineOptions.map((cuisine) => (
                <button
                  key={cuisine}
                  className={`chip ${filters.cuisineTypes.includes(cuisine) ? 'active' : ''}`}
                  onClick={() => toggleCuisineType(cuisine)}
                >
                  {cuisine}
                </button>
              ))}
            </div>
          </div>

          <div className="filter-section">
            <h4>가격대</h4>
            <select
              className="filter-select"
              value={filters.priceRange}
              onChange={(e) => handleFilterChange('priceRange', e.target.value)}
            >
              <option value="">전체</option>
              {priceOptions.map((price) => (
                <option key={price} value={price}>
                  {price}
                </option>
              ))}
            </select>
          </div>

          <div className="filter-section">
            <h4>분위기</h4>
            <select
              className="filter-select"
              value={filters.atmosphere}
              onChange={(e) => handleFilterChange('atmosphere', e.target.value)}
            >
              <option value="">전체</option>
              {atmosphereOptions.map((atm) => (
                <option key={atm} value={atm}>
                  {atm}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}
    </div>
  );
}

export default SearchBar;
