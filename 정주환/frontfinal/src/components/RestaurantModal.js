import React, { useEffect, useState } from 'react';
import { getRestaurantDetail, batchTranslateText } from '../services/api';
import './RestaurantModal.css';

function RestaurantModal({ restaurant, onClose, selectedLanguage = 'ko' }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [translatedData, setTranslatedData] = useState({});
  const [translating, setTranslating] = useState(false);

  useEffect(() => {
    if (restaurant && restaurant.id) {
      loadRestaurantDetail(restaurant.id);
    }
  }, [restaurant]);

  const loadRestaurantDetail = async (restaurantId) => {
    setLoading(true);
    try {
      const data = await getRestaurantDetail(restaurantId);
      setDetail(data);
    } catch (error) {
      console.error('상세 정보 로드 실패:', error);
    } finally {
      setLoading(false);
    }
  };

  // 언어가 변경되면 배치 번역 실행
  useEffect(() => {
    const translateModalData = async () => {
      if (selectedLanguage === 'ko') {
        setTranslatedData({});
        return;
      }

      const displayData = detail || restaurant;
      if (!displayData) return;

      setTranslating(true);

      try {
        // 모든 번역할 텍스트를 수집
        const textsToTranslate = [];

        // 식당 이름
        textsToTranslate.push(displayData.name || '');

        // 주소
        textsToTranslate.push(displayData.address || '');

        // 음식 종류
        textsToTranslate.push(displayData.cuisine_type || '');

        // 소개
        textsToTranslate.push(displayData.summary || '');

        // 메뉴 이름들
        const menuNames = [];
        if (displayData.menus && displayData.menus.length > 0) {
          displayData.menus.forEach(menu => {
            menuNames.push(menu.name || '');
          });
          textsToTranslate.push(...menuNames);
        }

        // 배치 번역 실행 (1번의 API 호출)
        const result = await batchTranslateText(textsToTranslate, selectedLanguage);
        const translations = result.translations;

        // 번역 결과를 분리
        const translatedData = {
          name: translations[0],
          address: translations[1],
          cuisine_type: translations[2],
          summary: translations[3]
        };

        // 메뉴 번역 결과 매핑
        if (displayData.menus && displayData.menus.length > 0) {
          translatedData.menus = displayData.menus.map((menu, index) => ({
            ...menu,
            translatedName: translations[4 + index]
          }));
        }

        setTranslatedData(translatedData);
      } catch (error) {
        console.error('번역 실패:', error);
      } finally {
        setTranslating(false);
      }
    };

    translateModalData();
  }, [selectedLanguage, detail, restaurant]);

  if (!restaurant) return null;

  const displayData = detail || restaurant;

  // 번역된 데이터가 있으면 사용, 없으면 원본 사용
  const getName = () => translatedData.name || displayData.name;
  const getAddress = () => translatedData.address || displayData.address;
  const getCuisineType = () => translatedData.cuisine_type || displayData.cuisine_type;
  const getSummary = () => translatedData.summary || displayData.summary;
  const getMenus = () => translatedData.menus || displayData.menus;

  // 섹션 제목 번역
  const getSectionTitles = () => {
    const titles = {
      ko: {
        location: '📍 위치',
        cuisine: '🍽️ 음식 종류',
        price: '💰 가격대',
        introduction: '📝 소개',
        menu: '🍴 메뉴',
        representative: '대표',
        loading: '상세 정보를 불러오는 중...',
        translating: '번역 중...',
        noAddress: '주소 정보 없음'
      },
      en: {
        location: '📍 Location',
        cuisine: '🍽️ Cuisine Type',
        price: '💰 Price Range',
        introduction: '📝 Introduction',
        menu: '🍴 Menu',
        representative: 'Signature',
        loading: 'Loading details...',
        translating: 'Translating...',
        noAddress: 'No address available'
      },
      ja: {
        location: '📍 位置',
        cuisine: '🍽️ 料理の種類',
        price: '💰 価格帯',
        introduction: '📝 紹介',
        menu: '🍴 メニュー',
        representative: '代表',
        loading: '詳細情報を読み込んでいます...',
        translating: '翻訳中...',
        noAddress: '住所情報なし'
      },
      zh: {
        location: '📍 位置',
        cuisine: '🍽️ 美食类型',
        price: '💰 价格范围',
        introduction: '📝 介绍',
        menu: '🍴 菜单',
        representative: '招牌',
        loading: '正在加载详细信息...',
        translating: '翻译中...',
        noAddress: '无地址信息'
      }
    };
    return titles[selectedLanguage] || titles.ko;
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>
          ✕
        </button>

        {loading ? (
          <div className="modal-loading">
            <div className="spinner"></div>
            <p>{getSectionTitles().loading}</p>
          </div>
        ) : translating ? (
          <div className="modal-loading">
            <div className="spinner"></div>
            <p>{getSectionTitles().translating}</p>
          </div>
        ) : (
          <>
            <div className="modal-header">
              {displayData.image_url && (
                <img
                  src={displayData.image_url}
                  alt={getName()}
                  className="modal-image"
                />
              )}
              <h2>{getName()}</h2>
              {displayData.rating && (
                <div className="modal-rating">
                  <span className="star">⭐</span>
                  <span>{displayData.rating.toFixed(1)}</span>
                </div>
              )}
            </div>

            <div className="modal-body">
              <div className="info-section">
                <h3>{getSectionTitles().location}</h3>
                <p>{getAddress() || getSectionTitles().noAddress}</p>
              </div>

              {getCuisineType() && (
                <div className="info-section">
                  <h3>{getSectionTitles().cuisine}</h3>
                  <p>{getCuisineType()}</p>
                </div>
              )}

              {displayData.price_range && (
                <div className="info-section">
                  <h3>{getSectionTitles().price}</h3>
                  <p>{displayData.price_range}</p>
                </div>
              )}

              {getSummary() && (
                <div className="info-section">
                  <h3>{getSectionTitles().introduction}</h3>
                  <p>{getSummary()}</p>
                </div>
              )}

              {getMenus() && getMenus().length > 0 && (
                <div className="info-section">
                  <h3>{getSectionTitles().menu}</h3>
                  <div className="menu-list">
                    {getMenus().map((menu, index) => (
                      <div key={index} className="menu-item">
                        <span className="menu-name">
                          {menu.translatedName || menu.name}
                          {menu.is_representative === 'Y' && <span className="badge-representative"> {getSectionTitles().representative}</span>}
                        </span>
                        {menu.price && (
                          <span className="menu-price">
                            {parseInt(menu.price).toLocaleString()}원
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default RestaurantModal;
