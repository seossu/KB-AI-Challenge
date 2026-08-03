import { useEffect, useRef, useState } from 'react';

/*
 * 네이버 지도 (동적). index.html 에서 Maps JS API 스크립트를 로드해야 합니다.
 * 클라이언트 ID가 없으면 window.naver 가 없으므로 안내 박스로 폴백합니다.
 */
export default function NaverMap({ lat, lng, name }) {
  const ref = useRef(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!window.naver || !window.naver.maps) {
      setFailed(true);
      return;
    }
    const { maps } = window.naver;
    const center = new maps.LatLng(lat, lng);
    const map = new maps.Map(ref.current, { center, zoom: 15 });
    new maps.Marker({ position: center, map, title: name });
  }, [lat, lng, name]);

  if (failed) {
    return (
      <div className="map-box">
        <div className="map-fallback">
          <div style={{ fontSize: 28 }}>🗺️</div>
          <b>{name}</b>
          <div style={{ fontSize: 13 }}>
            네이버 지도 API 키(ncpClientId)를 index.html에 설정하면<br />
            이 자리에 실제 지도가 표시됩니다.
          </div>
        </div>
      </div>
    );
  }
  return <div className="map-box"><div ref={ref} style={{ width: '100%', height: '100%' }} /></div>;
}
