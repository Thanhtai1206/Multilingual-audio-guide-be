"""
Dữ liệu khởi tạo.

- LANGUAGES: 16 ngôn ngữ (PRD yêu cầu 15+), mỗi ngôn ngữ có mã dịch máy và giọng Edge-TTS.
- SAMPLE_*: dữ liệu MẪU cho Chùa Linh Ứng Bãi Bụt (Sơn Trà, Đà Nẵng).
  !!! Tọa độ là ước lượng và nội dung mang tính minh họa. Nhóm cần đo tọa độ thật
  tại chùa (dùng Google Maps) và đối chiếu nội dung với tài liệu chính thức trước khi demo.
"""

LANGUAGES = [
    # code, name, native_name, translator_code, tts_voice
    ("vi", "Vietnamese", "Tiếng Việt", "vi", "vi-VN-HoaiMyNeural"),
    ("en", "English", "English", "en", "en-US-JennyNeural"),
    ("zh", "Chinese", "中文", "zh-CN", "zh-CN-XiaoxiaoNeural"),
    ("ja", "Japanese", "日本語", "ja", "ja-JP-NanamiNeural"),
    ("ko", "Korean", "한국어", "ko", "ko-KR-SunHiNeural"),
    ("fr", "French", "Français", "fr", "fr-FR-DeniseNeural"),
    ("de", "German", "Deutsch", "de", "de-DE-KatjaNeural"),
    ("es", "Spanish", "Español", "es", "es-ES-ElviraNeural"),
    ("ru", "Russian", "Русский", "ru", "ru-RU-SvetlanaNeural"),
    ("th", "Thai", "ไทย", "th", "th-TH-PremwadeeNeural"),
    ("it", "Italian", "Italiano", "it", "it-IT-ElsaNeural"),
    ("pt", "Portuguese", "Português", "pt", "pt-BR-FranciscaNeural"),
    ("id", "Indonesian", "Bahasa Indonesia", "id", "id-ID-GadisNeural"),
    ("ms", "Malay", "Bahasa Melayu", "ms", "ms-MY-YasminNeural"),
    ("hi", "Hindi", "हिन्दी", "hi", "hi-IN-SwaraNeural"),
    ("ar", "Arabic", "العربية", "ar", "ar-SA-ZariyahNeural"),
]

SAMPLE_POIS = [
    {
        "code": "CONG_TAM_QUAN",
        "name": "Cổng Tam Quan",
        "category": "gate",
        "latitude": 16.10010,
        "longitude": 108.27735,
        "trigger_radius_m": 25,
        "priority": 5,
        "sort_order": 1,
        "description": (
            "Chào mừng bạn đến với Chùa Linh Ứng Bãi Bụt trên bán đảo Sơn Trà, Đà Nẵng. "
            "Cổng Tam Quan là cửa ngõ đầu tiên của ngôi chùa. Theo quan niệm Phật giáo, ba lối đi "
            "tượng trưng cho Không quan, Vô tướng quan và Vô tác quan - nhắc người bước vào hãy để lại "
            "phiền muộn phía sau. Khi đi qua cổng, xin bạn giữ trật tự và ăn mặc lịch sự."
        ),
    },
    {
        "code": "TUONG_QUAN_AM",
        "name": "Tượng Phật Bà Quan Thế Âm",
        "category": "statue",
        "latitude": 16.10035,
        "longitude": 108.27790,
        "trigger_radius_m": 40,
        "priority": 10,
        "sort_order": 2,
        "description": (
            "Đây là công trình nổi bật nhất của chùa: tượng Phật Bà Quan Thế Âm cao khoảng 67 mét, "
            "đứng trên đài sen lớn, mặt hướng ra biển Đông. Người dân địa phương tin rằng Ngài che chở "
            "cho ngư dân ra khơi được bình an. Bên trong tượng có nhiều tầng thờ Phật. "
            "Từ chân tượng, bạn có thể ngắm toàn cảnh vịnh Đà Nẵng và thành phố."
        ),
    },
    {
        "code": "CHANH_DIEN",
        "name": "Chánh điện",
        "category": "hall",
        "latitude": 16.10060,
        "longitude": 108.27760,
        "trigger_radius_m": 30,
        "priority": 8,
        "sort_order": 3,
        "description": (
            "Chánh điện là nơi thờ Phật và diễn ra các nghi lễ chính của chùa. Kiến trúc mang phong cách "
            "chùa Việt truyền thống với mái cong lợp ngói và các chi tiết rồng phượng. "
            "Khi vào chánh điện, xin bạn bỏ giày dép, giữ yên lặng và không chụp ảnh khi đang có nghi lễ."
        ),
    },
    {
        "code": "VUON_LA_HAN",
        "name": "Vườn tượng Thập Bát La Hán",
        "category": "garden",
        "latitude": 16.10050,
        "longitude": 108.27720,
        "trigger_radius_m": 30,
        "priority": 6,
        "sort_order": 4,
        "description": (
            "Hai bên lối đi là mười tám vị La Hán được tạc bằng đá, mỗi vị một dáng vẻ và biểu cảm riêng. "
            "La Hán là những vị đã tu hành đắc đạo, đại diện cho các đức tính như nhẫn nại, trí tuệ và từ bi. "
            "Bạn hãy thử quan sát nét mặt của từng vị để cảm nhận sự sinh động của nghệ thuật điêu khắc."
        ),
    },
    {
        "code": "VUON_BONSAI",
        "name": "Vườn cây cảnh",
        "category": "garden",
        "latitude": 16.10075,
        "longitude": 108.27735,
        "trigger_radius_m": 30,
        "priority": 3,
        "sort_order": 5,
        "description": (
            "Khuôn viên chùa có nhiều cây cảnh và bonsai được chăm sóc công phu, tạo nên không gian xanh "
            "mát và thanh tịnh. Đây là nơi lý tưởng để nghỉ chân, chụp ảnh và tận hưởng gió biển. "
            "Xin đừng bẻ cành hay hái lá để giữ gìn cảnh quan chung."
        ),
    },
    {
        "code": "DIEM_NGAM_VINH",
        "name": "Điểm ngắm vịnh Đà Nẵng",
        "category": "viewpoint",
        "latitude": 16.10000,
        "longitude": 108.27830,
        "trigger_radius_m": 35,
        "priority": 4,
        "sort_order": 6,
        "description": (
            "Từ điểm này bạn có thể nhìn bao quát vịnh Đà Nẵng, bãi biển Mỹ Khê và ở xa là dãy núi "
            "Ngũ Hành Sơn. Buổi sáng sớm và lúc hoàng hôn là thời điểm đẹp nhất để chụp ảnh. "
            "Hãy cẩn thận khi đứng gần lan can."
        ),
    },
]


def _every_day(*periods: tuple[str, str]) -> list[dict]:
    """Cùng khung giờ cho cả 7 ngày trong tuần."""
    return [{"day": d, "open": o, "close": c} for d in range(7) for o, c in periods]


# Thông tin chi tiết từng điểm (giống thẻ địa điểm trên Google Maps).
# !!! DỮ LIỆU MẪU để demo - cần hỏi ban quản lý chùa giờ mở cửa thật của từng khu trước khi dùng.
SAMPLE_POI_DETAILS = {
    "CONG_TAM_QUAN": {
        "opening_hours": _every_day(("05:30", "21:00")),
        "entry_fee_vnd": 0,
        "visit_minutes": 5,
        "amenities": ["parking", "restroom", "wheelchair", "photo_ok", "dress_code"],
        "tips": "Bãi gửi xe nằm ngay cạnh cổng. Nên đến trước 8 giờ sáng hoặc sau 16 giờ để tránh nắng và đông khách. "
        "Ngày rằm và mùng một âm lịch chùa rất đông.",
    },
    "TUONG_QUAN_AM": {
        "opening_hours": _every_day(("06:00", "21:00")),
        "entry_fee_vnd": 0,
        "visit_minutes": 20,
        "amenities": ["stairs", "photo_ok", "shoes_off", "dress_code"],
        "tips": "Có nhiều bậc thang lên đài sen, người lớn tuổi nên đi chậm và nghỉ giữa chừng. "
        "Buổi trưa nền đá rất nóng, nên mang theo nón và nước uống.",
    },
    "CHANH_DIEN": {
        # Nghỉ trưa 11:30 - 13:30 (dữ liệu mẫu)
        "opening_hours": _every_day(("06:00", "11:30"), ("13:30", "21:00")),
        "entry_fee_vnd": 0,
        "visit_minutes": 15,
        "amenities": ["shoes_off", "quiet_zone", "no_photo_ceremony", "dress_code"],
        "tips": "Chánh điện đóng cửa nghỉ trưa từ 11:30 đến 13:30. Giờ tụng kinh buổi chiều khoảng 18:00, "
        "du khách vẫn được vào nhưng cần giữ yên lặng và không chụp ảnh.",
    },
    "VUON_LA_HAN": {
        "opening_hours": _every_day(("06:00", "21:00")),
        "entry_fee_vnd": 0,
        "visit_minutes": 10,
        "amenities": ["wheelchair", "shade", "photo_ok"],
        "tips": "Lối đi bằng phẳng, xe lăn và xe đẩy em bé đi được. Không trèo lên bệ tượng để chụp ảnh.",
    },
    "VUON_BONSAI": {
        "opening_hours": _every_day(("06:00", "18:00")),
        "entry_fee_vnd": 0,
        "visit_minutes": 10,
        "amenities": ["shade", "restroom", "drinking_water", "photo_ok"],
        "tips": "Có ghế đá nghỉ chân dưới bóng cây. Nhà vệ sinh ở cuối vườn, gần lối ra bãi xe.",
    },
    "DIEM_NGAM_VINH": {
        "opening_hours": _every_day(("05:00", "21:00")),
        "entry_fee_vnd": 0,
        "visit_minutes": 15,
        "amenities": ["photo_ok", "wheelchair"],
        "tips": "Đẹp nhất lúc bình minh (khoảng 5:15 - 6:00) và hoàng hôn. Gió biển khá mạnh, "
        "giữ chặt điện thoại và mũ nón khi đứng gần lan can.",
    },
}

SAMPLE_TOURS = [
    {
        "code": "TOUR_CO_BAN",
        "name": "Lộ trình cơ bản 30 phút",
        "description": "Tham quan các điểm chính của chùa dành cho khách có ít thời gian.",
        "poi_codes": ["CONG_TAM_QUAN", "VUON_LA_HAN", "CHANH_DIEN", "TUONG_QUAN_AM"],
        "estimated_minutes": 30,
    },
    {
        "code": "TOUR_DAY_DU",
        "name": "Lộ trình đầy đủ 60 phút",
        "description": "Khám phá toàn bộ khuôn viên chùa và ngắm cảnh vịnh Đà Nẵng.",
        "poi_codes": ["CONG_TAM_QUAN", "VUON_LA_HAN", "CHANH_DIEN", "VUON_BONSAI", "TUONG_QUAN_AM", "DIEM_NGAM_VINH"],
        "estimated_minutes": 60,
    },
]

SAMPLE_ARTICLES = [
    {
        "title": "Giới thiệu chung về Chùa Linh Ứng Bãi Bụt",
        "content": "Chùa Linh Ứng Bãi Bụt nằm trên bán đảo Sơn Trà, quận Sơn Trà, thành phố Đà Nẵng, nhìn ra vịnh Đà Nẵng. "
        "Đây là một trong ba ngôi chùa mang tên Linh Ứng ở Đà Nẵng, cùng với chùa Linh Ứng Non Nước (Ngũ Hành Sơn) "
        "và chùa Linh Ứng Bà Nà. Chùa được xây dựng từ khoảng năm 2004 và hoàn thành khoảng năm 2010 "
        "(dữ liệu mẫu, cần đối chiếu). Công trình nổi bật nhất là tượng Phật Bà Quan Thế Âm cao khoảng 67 mét "
        "hướng ra biển. Chùa là điểm tham quan tâm linh nổi tiếng của Đà Nẵng, thu hút đông du khách trong và ngoài nước.",
        "tags": ["giới thiệu", "lịch sử", "tổng quan"],
    },
    {
        "title": "Giờ mở cửa",
        "content": "Chùa mở cửa đón khách hằng ngày từ 6 giờ sáng đến 21 giờ tối (dữ liệu mẫu, cần xác nhận). "
        "Vào các ngày rằm và mùng một âm lịch, chùa thường đông khách hơn.",
        "tags": ["giờ", "mở cửa", "thời gian"],
    },
    {
        "title": "Quy định trang phục",
        "content": "Du khách nên mặc trang phục kín đáo, lịch sự: không mặc áo hai dây, quần đùi hay váy quá ngắn. "
        "Khi vào chánh điện cần bỏ giày dép và giữ yên lặng.",
        "tags": ["trang phục", "quy định", "ăn mặc"],
    },
    {
        "title": "Cách di chuyển đến chùa",
        "content": "Chùa nằm trên bán đảo Sơn Trà, cách trung tâm thành phố Đà Nẵng khoảng 10 km. "
        "Bạn có thể đi taxi, xe máy hoặc xe đạp theo đường Hoàng Sa. Đường lên chùa có dốc, cần lái cẩn thận.",
        "tags": ["di chuyển", "đường đi", "taxi", "xe"],
    },
    {
        "title": "Gửi xe và nhà vệ sinh",
        "content": "Bãi gửi xe nằm ngay dưới chân chùa, gần Cổng Tam Quan. Nhà vệ sinh công cộng ở khu vực bãi xe "
        "và gần vườn cây cảnh.",
        "tags": ["gửi xe", "đỗ xe", "nhà vệ sinh", "toilet"],
    },
    {
        "title": "Vé tham quan và thuyết minh tự động",
        "content": "Vào chùa không thu phí. Ứng dụng thuyết minh tự động đa ngôn ngữ có phí sử dụng, "
        "thanh toán online hoặc trả tiền mặt tại quầy để nhận mã truy cập; mã dùng được trong 24 giờ.",
        "tags": ["vé", "giá", "phí", "thanh toán", "mã"],
    },
    {
        "title": "Ăn chay và quà lưu niệm",
        "content": "Gần khu vực bãi xe có quầy nước và quà lưu niệm. Vui lòng không mang đồ ăn mặn vào khu vực chánh điện.",
        "tags": ["ăn", "uống", "lưu niệm", "mua"],
    },
]
