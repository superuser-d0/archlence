"""Archlence'ın hafif, yerel ve bağımlılıksız çeviri katmanı.

Türkçe metinler kaynak anahtar olarak kullanılır. Bu yaklaşım mevcut arayüzü
parça parça taşımayı kolaylaştırırken eksik bir çeviride kullanıcıya anlamsız
bir anahtar göstermek yerine Türkçe metne güvenli biçimde geri döner.

SÖZLEŞME — ikisi birlikte geçerli:

  * `tr(metin)` YALNIZ TAM ANAHTAR eşleşmesi yapar. Bilinmeyen metinde kaynağa
    döner. Alt dize değiştirmez.
  * Dinamik cümleler `trf(sablon, **parametre)` ile kurulur: ÖNCE şablon
    çevrilir, SONRA parametreler yerleştirilir. Parametre değerleri bir daha
    ASLA çeviriden geçmez.

NEDEN: `tr()` eskiden tam eşleşme bulamayınca sözlükteki Türkçe parçaları metin
içinde sırayla değiştiriyordu ve çağıranlar f-string'i ÖNCE kurup sonra
çeviriye veriyordu. Sonuç, kullanıcının KENDİ VERİSİNİN çevrilmesiydi —
ölçüldü: "Nakit" adlı hesap İngilizce arayüzde "Cash", "Ayarlar" adlı abonelik
"Settings" görünüyordu. Cümleler de bozuluyordu: "Tür Seç: Hisse Senedi"
"Select Type: Stock Senedi" oluyordu, yani yarısı çevrilmiş bir melez.

Parça değiştirme ayrıca Türkçe cümle SIRASINI İngilizceye taşıyordu. Şablon
yaklaşımında sıra tamamen çeviriye ait: "{name} hesabı eklendi." karşılığı
"Account added: {name}" olabilir.
"""

import re

SUPPORTED_LANGUAGES = {"tr": "Türkçe", "en": "English"}
_language = "tr"

#: Şablonlarda izin verilen tek yer tutucu biçimi: `{ad}`.
#:
#: Biçim belirteci (`{amount:,.2f}`) BİLEREK desteklenmiyor. Sayı/tarih/para
#: biçimlendirmesi çağıran tarafta, bugünkü davranışıyla yapılır ve sonucu
#: hazır METİN olarak parametreye geçer; böylece bu katman biçimlendirme
#: politikasına hiç karışmaz ve şablonların çevirmen tarafında okunması kolay
#: kalır.
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


EN = {
    # Araçlar ızgarasındaki bütçe karesi (iki satır, diğer kareler gibi).
    "Aylık\nBütçe": "Monthly\nBudget",
    "Güvenli Giriş": "Secure Sign In",
    "Yerel Şifreni Belirle": "Set Your Local Password",
    "Şifre": "Password",
    "Şifre Tekrar": "Confirm Password",
    "ŞİFRE OLUŞTUR": "CREATE PASSWORD",
    "Şifre yalnızca bu cihazda saklanır; Archlence verilerinizi bir sunucuya göndermez.": "Your password is stored only on this device; Archlence does not send your data to a server.",
    "Şifre en az 4 karakter olmalıdır.": "Password must be at least 4 characters long.",
    "Şifre en az 1 büyük harf içermelidir.": "Password must contain at least 1 uppercase letter.",
    "Şifre en az 1 özel karakter (örn. . veya ,) içermelidir.": "Password must contain at least 1 special character (e.g. . or ,).",
    "Şifreler eşleşmiyor.": "Passwords do not match.",
    "Hatalı Şifre!": "Incorrect password!",
    "Şifreni mi unuttun? Sağ üstteki Ayarlar > Şifre ve Verileri Sıfırla yolunu kullanabilirsin. Tüm yerel finans verilerin silinir.": "Forgot your password? Use Settings > Reset Password and Data in the top-right corner. All local financial data will be deleted.",
    "Şifre ve Verileri Sıfırla": "Reset Password and Data",
    "Şifre dahil tüm yerel finans verilerini kalıcı olarak siler": "Permanently deletes the password and all local financial data",
    "Şifre Değiştir": "Change Password",
    "Şifrenizi buradan yenileyebilirsiniz.": "You can renew your password here.",
    "Yeni Şifre": "New Password",
    "Yeni Şifre Tekrar": "Confirm New Password",
    "Şifre başarıyla değiştirildi. Lütfen tekrar giriş yapın.": "Password successfully changed. Please log in again.",
    "En az 4 karakter, 1 büyük harf ve 1 özel karakter": "At least 4 chars, 1 uppercase and 1 special char",
    "GİRİŞ YAP": "SIGN IN",
    "Ayarlar": "Settings",
    "Karanlık Mod": "Dark Mode",
    "Ana Sayfa": "Home",
    "Archlence'ta ara...": "Search in Archlence...",
    # Arama çubuğu — kapsam bilerek dar olduğu için ipucu metni de ne
    # aradığını açıkça söylüyor ("Archlence'ta ara" her şeyi arıyormuş gibi
    # duruyordu ve hiçbir şey aramıyordu).
    "Hesap, kategori veya işlem ara...": "Search accounts, categories or transactions...",
    "Sonuç bulunamadı": "No results found",
    "Hesap, kategori ve son işlemlerde arandı": "Searched accounts, categories and recent transactions",
    "Hesap": "Account",
    "İşlem": "Transaction",
    # Bildirim zili
    "Bekleyen bildirim yok": "No pending notifications",
    "Bildirimler yüklenemedi": "Could not load notifications",
    "Bekleyen işlem": "Pending transaction",
    "Yaklaşan ödeme": "Upcoming payment",
    "Gecikti": "Overdue",
    "Cüzdanım": "My Wallet",
    "Toplam Bakiye": "Total Balance",
    "Aylık Gider Değişimi": "Monthly Expense Change",
    "Dikkat: Bakiye Negatif!": "Warning: Negative Balance!",
    "Bugün": "Today",
    "Değişim": "Change",
    # Eskiden "Değişim" + "Bugün" parçalarının ayrı ayrı
    # değiştirilmesiyle oluşuyordu; artık tam anahtar.
    "Değişim (Bugün)": "Change (Today)",
    "1 Hafta": "1 Week",
    "1 Ay": "1 Month",
    "1 Yıl": "1 Year",
    "Toplam": "Total",
    "Algoritmik Öngörü": "Algorithmic Forecast",
    "Veriler analiz ediliyor...": "Analyzing your data...",
    "Son 3 ayın istatistiğine göre ay sonu öngörüsü: en az 3 aylık işlem geçmişi biriktiğinde burada görünecek.": "Based on the last 3 months of statistics, the month-end forecast will appear here once at least 3 months of transaction history has accumulated.",
    "Son 3 ayın istatistiğine göre bu ay sonunda bakiyenizin {month_end} olması bekleniyor. Dikkat: Model bakiyenizin eksiye düşebileceğini gösteriyor, harcamalarınızı gözden geçirin.": "Based on the last 3 months of statistics, your balance is expected to be {month_end} at the end of this month. Warning: The model indicates that your balance may fall below zero; review your spending.",
    "Son 3 ayın istatistiğine göre mevcut harcama eğiliminiz sürerse bu ay sonunda bakiyeniz {month_end} seviyesine gerileyebilir.": "Based on the last 3 months of statistics, your balance may fall to {month_end} by the end of this month if your current spending trend continues.",
    "Son 3 ayın istatistiğine göre bu ay sonunda cebinizde {month_end} kalacak; bunu bir yatırım aracı olarak değerlendirebilirsiniz.": "Based on the last 3 months of statistics, you are expected to have {month_end} left at the end of this month; you could consider putting it toward an investment.",
    "Son 3 ayın istatistiğine göre bu ay sonunda bakiyenizin yaklaşık {month_end} olması bekleniyor.": "Based on the last 3 months of statistics, your balance is expected to be approximately {month_end} at the end of this month.",
    "Finansal Sağlık Skoru": "Financial Health Score",
    "Hesaplanıyor...": "Calculating...",
    "Tasarruf oranı, borç/gelir ve gider oynaklığı birlikte değerlendirilir.": "Savings rate, debt-to-income ratio, and spending volatility are evaluated together.",
    "Aktif Aboneliklerim": "My Active Subscriptions",
    "Aktif aboneliğiniz bulunmuyor.": "You have no active subscriptions.",
    "Sonraki ödeme:": "Next payment:",
    "Ödeme günü 1 ile 31 arasında olmalıdır.": "Payment day must be between 1 and 31.",
    "Tekrarlama günü 1 ile 31 arasında olmalıdır.": "Recurrence day must be between 1 and 31.",
    "Ayrılmış abonelik gideri:": "Reserved subscription expense:",
    "Harcama limitiniz:": "Spending limit:",
    "Kategori seçin": "Select a category",
    "Tutar": "Amount",
    "Tek seferlik": "One-time",
    "Her ay": "Every month",
    "Daha fazla seçenek": "More options",
    "Daha az seçenek": "Fewer options",
    "Geçmişe göre tutar öner": "Suggest an amount from history",
    "Bütçe kalemi ekle": "Add budget item",
    "BÜTÇEYE EKLE": "ADD TO BUDGET",
    "Kategori veya serbest metin seç": "Choose a category or free text",
    "Serbest plan adı": "Custom plan name",
    "Takvim": "Calendar",
    "{} işlem bulundu.": "{} transaction(s) found.",
    "Serbest metin gir": "Enter free text",
    "Lütfen tutarları geçerli bir sayı olarak girin.": "Please enter amounts as a valid number.",
    "Geçen ayın kalanını/aşımını devret": "Carry over last month's remainder/overrun",
    "Her ay otomatik tekrarla (şablon)": "Repeat automatically every month (template)",
    "Uyarı eşiği (%)": "Alert threshold (%)",
    "ÖNER": "SUGGEST",
    "Öneri için önce kategori seçin.": "Select a category before requesting a suggestion.",
    "Bu kategori için yeterli geçmiş yok.": "There is not enough history for this category.",
    "Sabit Giderler (Abonelikler)": "Fixed Expenses (Subscriptions)",
    "Planlanan Kalemler": "Planned Items",
    "Bu ay için ayrılmış abonelik gideri yok.": "No subscription expense is reserved for this month.",
    "Henüz planlanan kalem yok.": "No planned items yet.",
    "YÖNET": "MANAGE",
    "Şablon": "Template",
    "Gerçekleşen": "Actual",
    "geçen aydan devir": "carried over from last month",
    "Aktif abonelikler ana sayfadaki karttan yönetilebilir.": "Active subscriptions can be managed from the card on the home screen.",
    "Tutar pozitif, uyarı eşiği 1-100 arasında olmalıdır.": "Amount must be positive and the alert threshold must be between 1 and 100.",
    "Şablon seçildi; belirli aylara kopyalama uygulanmadı.": "Template selected; copying to specific months was skipped.",
    "Geçmiş / Trend": "History / Trend",
    "Gri: Planlanan · Renkli: Gerçekleşen": "Gray: Planned · Colored: Actual",
    "6 Aylık Bütçe Trendi": "6-Month Budget Trend",
    "Olağandışı Harcamalar": "Unusual Spending",
    "Tespit edilen gizli abonelik yok.": "No hidden subscriptions detected.",
    "Olağandışı harcama tespit edilmedi.": "No unusual spending detected.",
    "1 gün kaldı": "1 day left",
    " gün kaldı": " days left",
    "Gecikti (": "Overdue (",
    "1 gün)": "1 day)",
    " gün)": " days)",
    "Aylık Bütçe Planı": "Monthly Budget Plan",
    "Ay seçin ve plan oluşturun...": "Select a month and create a plan...",
    "Aktif Borçlarım": "My Active Debts",
    "Henüz aktif bir borcunuz bulunmuyor.": "You have no active debts yet.",
    "Yaklaşan Ödemeler": "Upcoming Payments",
    "Yaklaşan ödeme bulunmuyor.": "No upcoming payments.",
    "Aktif Gelirlerim": "My Active Incomes",
    "Aktif geliriniz bulunmuyor.": "You have no active incomes.",
    "Son İşlemler": "Recent Transactions",
    "Bu dönemde işlem bulunmuyor.": "No transactions in this period.",
    "Günlük": "Daily",
    "Haftalık": "Weekly",
    "Aylık": "Monthly",
    "Varlıklarım": "My Assets",
    "Gelir": "Income",
    "Gider": "Expense",
    "Net Bakiye": "Net Balance",
    "Detaylar": "Details",
    "Hayat Boyu": "All Time",
    "Toplam Varlık": "Total Assets",
    "Veriler yükleniyor...": "Loading data...",
    "Aktif Varlıklarım": "My Active Assets",
    "Yükleniyor...": "Loading...",
    "Varlık Geçmişi": "Asset History",
    "Henüz varlık işlemi bulunmuyor.": "No asset transactions yet.",
    "Toplam Gelir": "Total Income",
    "Toplam Gider": "Total Expenses",
    "Tasarruf Oranı": "Savings Rate",
    "Aylık Gelir Amacı": "Monthly Income Target",
    "Kartlarım": "My Cards",
    "Nakit": "Cash",
    "Banka": "Bank",
    "Kart Borcu": "Card Debt",
    "Net Servet": "Net Worth",
    "+ EKLE": "+ ADD",
    "Hesaplarım": "My Accounts",
    "Araçlar": "Tools",
    "Hesaplama Araçları": "Financial Tools",
    "Hesap\nMakinesi": "Calculator",
    "Faiz\nGetirisi": "Interest\nReturn",
    "Bileşik\nFaiz": "Compound\nInterest",
    "Kredi\nHesaplama": "Loan\nCalculator",
    "Birikim\nHedefi": "Savings\nGoal",
    "What-If\nSandbox": "What-If\nSandbox",
    "Verileri\nSıfırla": "Reset\nData",
    "Kategori Ayarları": "Category Settings",
    "Görünüm Ayarları": "Appearance",
    "Premium Mavi Tema": "Premium Blue Theme",
    "Kapalıyken standart tema kullanılır": "Uses the standard theme when disabled",
    "Veriler ve Gizlilik": "Data & Privacy",
    "Şifreleme Anahtarı": "Encryption Key",
    "Bakiye Geçmişi": "Balance History",
    "Bize Ulaşın": "Contact Us",
    "Çıkış Yap": "Sign Out",
    "Kategori Adı": "Category Name",
    "Ana Kaynak Mı?": "Primary Source?",
    "Dil": "Language",
    "Uygulama Dili": "App Language",
    "Türkçe": "Turkish",
    "İngilizce": "English",
    "VAZGEÇ": "CANCEL",
    "KAYDET": "SAVE",
    "KAPAT": "CLOSE",
    "İPTAL": "CANCEL",
    "EKLE": "ADD",
    "GERİ": "BACK",
    "HESAPLA": "CALCULATE",
    "SİL": "DELETE",
    "ÖDE": "PAY",
    "DURDUR": "STOP",
    "YOKSAY": "DISMISS",
    "GÖRDÜM": "SEEN",
    "ÖZEL ARALIK": "CUSTOM RANGE",
    "TARİHTE ARA": "BALANCE ON DATE",
    "TARİH SEÇ": "SELECT DATE",
    "TARİH GİR": "INPUT DATE",
    "TAMAM": "OK",
    "What-If Sandbox": "What-If Sandbox",
    "Gelir değişimi (%)": "Income change (%)",
    "Gider değişimi (%)": "Expense change (%)",
    "Artış için pozitif, azalış için negatif değer": "Use a positive value for an increase and a negative value for a decrease",
    "Azalış için negatif değer": "Use a negative value for a decrease",
    "Tek seferlik gelir/gider (₺)": "One-time income/expense (₺)",
    "Gelir pozitif, gider negatif girilir": "Enter income as positive and expense as negative",
    "30 Gün": "30 Days",
    "90 Gün": "90 Days",
    "365 Gün": "365 Days",
    "Senaryoyu görmek için HESAPLA'ya basın.": "Press CALCULATE to view the scenario.",
    "Projeksiyon verileri henüz hazır değil.": "Projection data is not ready yet.",
    "Senaryo hesaplanamadı.": "The scenario could not be calculated.",
    "Taban senaryoya göre": "Compared with the baseline",
    "\nDikkat: Bu senaryoda varlık negatife düşüyor.": "\nWarning: wealth becomes negative in this scenario.",
    "Yeterli veri yok": "Not enough data",
    "Skor hesaplamak için henüz yeterli veri yok. Birkaç işlem ekleyince burada görünecek.": "There is not enough data to calculate a score yet. It will appear here after you add a few transactions.",
    "0'dan büyük bir tutar girin!": "Enter an amount greater than zero!",
    "ABONELİĞE EKLE": "ADD SUBSCRIPTION",
    "Aktif Varlık hesabı salt okunurdur ve ödeme yöntemi olamaz.": "The Active Assets account is read-only and cannot be used as a payment method.",
    "Alım Bilgileri": "Purchase Details",
    "Alım Fiyatı (₺ / adet)": "Purchase Price (₺ / unit)",
    "Alım Fiyatı (₺)": "Purchase Price (₺)",
    "Ana Para (₺)": "Principal (₺)",
    "Ara: Hisse adı veya sembol...": "Search by stock name or symbol...",
    "Ara: Kripto adı veya sembol...": "Search by crypto name or symbol...",
    "Aylık Eklenen Tutar (₺)": "Monthly Contribution (₺)",
    "Aylık Faiz Oranı (%)": "Monthly Interest Rate (%)",
    "BIST 100 — Hisse Seç": "BIST 100 — Select Stock",
    "Bakiyenin Aktarılacağı Hesap": "Account to Receive the Balance",
    "Bakiyenin aktarılabileceği vadesiz hesap bulunamadı.": "No checking account is available to receive the balance.",
    "Bileşik Faiz": "Compound Interest",
    "Birikim hedefi belirlenmedi — Araçlar sekmesinden hedef ekleyebilirsin!": "No savings goal yet — add one from the Tools tab!",
    "Borç Olarak Ekle": "Add as Debt",
    "Borç başarıyla eklendi!": "Debt added successfully!",
    "Borç başarıyla ödendi!": "Debt paid successfully!",
    "Borç eklenirken hata oluştu!": "Could not add the debt!",
    "Borç tamamen kapatıldı!": "Debt paid off completely!",
    "Borç/Kredi Adı (Örn: Araba Kredisi)": "Debt/Loan Name (e.g. Car Loan)",
    "Bu abonelik zaten kayıtlı.": "This subscription is already tracked.",
    "Bu aralıkta bakiye hareketi yok.": "No balance activity in this period.",
    "Bu borç zaten tamamen ödenmiş!": "This debt has already been paid off!",
    "Bu isimde aktif bir aboneliğiniz zaten var!": "You already have an active subscription with this name!",
    "Bu işlem türü için uygun bir hesap bulunamadı.": "No suitable account was found for this transaction type.",
    "Bu kartta henüz hareket yok.": "No transactions on this card yet.",
    "Bu kartta henüz taksitli işlem bulunmuyor": "No installment purchases on this card yet",
    "Bu sıklık otomatik takibe alınamıyor.": "This frequency cannot be tracked automatically.",
    "Bu tutar her dönem otomatik eklensin mi?": "Add this amount automatically every period?",
    "Bütçe Planlayıcı": "Budget Planner",
    "CSV Olarak Dışa Aktar": "Export as CSV",
    "CSV'den İçe Aktar": "Import from CSV",
    "Dosyada içe aktarılabilir işlem bulunamadı!": "No importable transactions found in the file!",
    "Düzenli Eklenecek Tutar (₺)": "Recurring Contribution (₺)",
    "Dışa aktarma sırasında hata oluştu!": "An error occurred during export!",
    "Dışa aktarılacak kayıt bulunamadı.": "No records available to export.",
    "Fiyat alınıyor…": "Fetching price…",
    "Fiyatlar anlık olarak güncelleniyor...": "Updating live prices...",
    "Son Güncelleme: —": "Last updated: —",
    "Son Güncelleme: ": "Last updated: ",
    "Manuel Yenile": "Refresh manually",
    "Gelecek Ödemeler": "Future Payments",
    "Gelişmiş": "Advanced",
    "Geçerli bir sayı girin!": "Enter a valid number!",
    "Geçerli bir tutar girin!": "Enter a valid amount!",
    "Geçersiz fiyat veya miktar!": "Invalid price or quantity!",
    "Geçersiz tutar.": "Invalid amount.",
    "Geçmiş okunamadı.": "Could not load history.",
    "Güncellenemedi": "Unavailable",
    "Güncellenirken hata oluştu!": "An error occurred while updating!",
    "Hedef Adı (Örn: Raspberry Pi Projesi)": "Goal Name (e.g. Raspberry Pi Project)",
    "Hedef Miktar (₺)": "Target Amount (₺)",
    "Hedef tutar 0'dan büyük olmalıdır!": "The target amount must be greater than zero!",
    "Henüz hesap eklenmedi — yukarıdaki butondan ekleyebilirsin.": "No accounts yet — use the button above to add one.",
    "Soru, öneri ve hata bildirimleri için GitHub sayfamızı kullanabilirsiniz:\n\n[b]github.com/superuser-d0/archlence[/b]": "For questions, feedback, or bug reports, use our GitHub page:\n\n[b]github.com/superuser-d0/archlence[/b]",
    "Hisse eklendi! Fiyatlar güncelleniyor…": "Stock added! Updating prices…",
    "Hisse eklenirken hata oluştu!": "Could not add the stock!",
    "Kalem Adı (Örn: Maaş, Kira)": "Item Name (e.g. Salary, Rent)",
    "Kalem adı boş olamaz!": "Item name cannot be empty!",
    "Kategori Seç": "Select Category",
    "Kredi Kartı": "Credit Card",
    "Kredi Kartını Sil": "Delete Credit Card",
    "Kredi Tutarı (₺)": "Loan Amount (₺)",
    "Kredi kartı bulunamadı.": "Credit card not found.",
    "Kredi kartı silindi.": "Credit card deleted.",
    "Kripto eklendi! Fiyatlar güncelleniyor…": "Crypto added! Updating prices…",
    "Kripto eklenirken hata oluştu!": "Could not add the crypto asset!",
    "Lütfen 0'dan büyük değerler girin!": "Enter values greater than zero!",
    "Lütfen 0'dan büyük tutarlar girin!": "Enter amounts greater than zero!",
    "Lütfen ad ve tutar girin!": "Enter a name and amount!",
    "Lütfen bir CSV dosyası seçin!": "Select a CSV file!",
    "Lütfen bir hisse seçin!": "Select a stock!",
    "Lütfen bir kategori seçin!": "Select a category!",
    "Lütfen bir kripto para seçin!": "Select a cryptocurrency!",
    "Lütfen geçerli bir hedef tutar girin!": "Enter a valid target amount!",
    "Lütfen geçerli bir sayı girin!": "Enter a valid number!",
    "Lütfen geçerli sayılar girin!": "Enter valid numbers!",
    "Lütfen süre girin!": "Enter a duration!",
    "Lütfen tutar giriniz.": "Enter an amount.",
    "Lütfen tüm alanları sayılarla doldurun!": "Fill in every field with valid numbers!",
    "Masraf Adı (Örn: Ekspertiz)": "Expense Name (e.g. Appraisal)",
    "Mevcut kalemi diğer aylara da uygula": "Apply this item to other months",
    "Miktar 0'dan büyük olmalıdır!": "Amount must be greater than zero!",
    "Onaylamak için büyük harflerle SİL yazın": "Type DELETE in uppercase to confirm",
    "Otomatik düşecek": "Will be deducted automatically",
    "Otomatik Ödeme": "Auto Pay",
    "Otomatik ödeme ayarları güncellendi!": "Auto-pay settings updated!",
    "PDF İNDİR": "DOWNLOAD PDF",
    "PORTFÖYE EKLE": "ADD TO PORTFOLIO",
    "Para yatırabileceğiniz vadesiz/nakit hesabı bulunamadı.": "No checking/cash account is available for this deposit.",
    "Portföyünüz şu an boş.\nİlk yatırımınızı ekleyerek değerini canlı takip edin!": "Your portfolio is empty.\nAdd your first investment to track its live value!",
    "Portföyünüze eklemek istediğiniz varlık türünü seçin.": "Choose the type of asset you want to add to your portfolio.",
    "Cüzdan Bakiyesi": "Wallet Balance",
    "Bu varlık için girdiğiniz toplam tutar cüzdan bakiyenizden düşülsün mü?\n\nYeni satın aldığınız bir varlıksa Evet; daha önce sahip olduğunuz bir varlığı uygulamaya ekliyorsanız Hayır'ı seçin.": "Should the total amount entered for this asset be deducted from your wallet balance?\n\nChoose Yes for a newly purchased asset, or No if you are adding an asset you already owned.",
    "HAYIR, DÜŞME": "NO, DON'T DEDUCT",
    "EVET, DÜŞ": "YES, DEDUCT",
    "SADECE SİL": "DELETE WITHOUT REFUND",
    "SEÇ  ✓": "SELECT  ✓",
    "Satış fiyatı (₺ / adet)": "Sale Price (₺ / unit)",
    "Satış işlemi başarısız!": "Sale failed!",
    "Seçilen: 1 Taksit": "Selected: 1 Installment",
    "Silme işlemi iptal edildi. Onay için SİL yazmalısınız.": "Deletion cancelled. Type DELETE to confirm.",
    "Sistem sıfırlandı!": "System reset complete!",
    "Sistemi Sıfırla": "Reset System",
    "Sonuç bekleniyor...": "Waiting for calculation...",
    "Sonuç yok": "No results",
    "Süre (Ay)": "Duration (Months)",
    "Süre (Yıl)": "Duration (Years)",
    "Süre 1 aydan büyük olmalı!": "Duration must be longer than one month!",
    "SİL yazınız": "Type DELETE",
    "Taksit Öde": "Pay Installments",
    "Taşıt": "Vehicle",
    "Tek Çekim": "Single Payment",
    "Taksitli": "Installments",
    "Basit": "Simple",
    "Konut": "Mortgage",
    "İhtiyaç": "Personal",
    "Tekrarlanan Ödeme mi?": "Recurring Payment?",
    "Tekrarlanan Gelir mi?": "Recurring Income?",
    "Gelir Adı (örn: Maaş)": "Income Name (e.g. Salary)",
    "Her Ayın Hangi Günü Ödenecek? (1-31)": "Which Day of Each Month Will It Be Paid? (1-31)",
    "Her Ayın Hangi Günü Yatacak? (1-31)": "Which Day of Each Month Will It Be Deposited? (1-31)",
    "Vadesi Gelince Otomatik Ekle": "Add Automatically When Due",
    "Otomatik eklenecek": "Will be added automatically",
    "EKLE": "ADD",
    "Bu Ay Dahil Edilsin mi?": "Include This Month?",
    "BU AYI DAHİL ET": "INCLUDE THIS MONTH",
    "BU AYI DAHİL ETME": "DON'T INCLUDE THIS MONTH",
    "Bu ayki gelir hesaba eklensin mi?\n\n“BU AYI DAHİL ET” seçilirse bu ayın günü geçtiyse gelir hemen, gelmediyse seçilen günde eklenir.": "Should this month's income be added to the account?\n\nIf “INCLUDE THIS MONTH” is selected, it will be added immediately when the chosen day has passed, or on the chosen day when it has not.",
    "Tekrarlanan gelir kaydedildi; bu ay dahil edilmedi.": "Recurring income saved; this month was not included.",
    "Tekrarlanan ödeme durduruldu.": "Recurring payment stopped.",
    "Top 100 Kripto — Seç": "Top 100 Crypto — Select",
    "Toplam Tutar (₺)": "Total Amount (₺)",
    "Tutar (₺)": "Amount (₺)",
    "Ödenecek Tutar (₺)": "Payment Amount (₺)",
    "Tutar 0'dan büyük olmalı!": "Amount must be greater than zero!",
    "Tutar 0'dan büyük olmalıdır.": "Amount must be greater than zero.",
    "Tüm Verileri Sıfırla": "Reset All Data",
    "Tüm işlemler, varlıklar, borçlar ve hedefler kalıcı olarak silinecektir. Emin misiniz?": "All transactions, assets, debts, and goals will be permanently deleted. Are you sure?",
    "Tüm veriler başarıyla silindi!": "All data was deleted successfully!",
    "Tüm veriler silinecek! Onaylıyor musunuz?": "All data will be deleted! Do you want to continue?",
    "Vade (Gün)": "Term (Days)",
    "Vadesi Gelince Otomatik Düş": "Deduct Automatically When Due",
    "Varlık Adı (isteğe bağlı)": "Asset Name (optional)",
    "Varlık eklendi! Fiyatlar güncelleniyor…": "Asset added! Updating prices…",
    "Varlık eklenirken hata oluştu!": "Could not add the asset!",
    "Varlıklar hazırlanıyor…": "Preparing assets…",
    "Varlığı Sat": "Sell Asset",
    "Veriler dışa aktarılıyor...": "Exporting data...",
    "Yeni Bir İşlem Ekle": "Add Transaction",
    "Yeni Varlık Ekle": "Add New Asset",
    "Yıllık": "Yearly",
    "Yıllık Faiz Oranı (%)": "Annual Interest Rate (%)",
    "Çok Seferlik": "Installments",
    "Ödeme Planı": "Payment Schedule",
    "Ödeme Tipi": "Payment Type",
    "Ödeme yapabileceğiniz vadesiz/nakit hesabınız bulunmamaktadır.": "You do not have a checking/cash account available for payment.",
    "Önbellek hazırlanıyor…": "Preparing cache…",
    "Önce hesaplama yapın!": "Run the calculation first!",
    "Özel Masraf Ekle": "Add Custom Expense",
    "Özel Masraflar (0/10)": "Custom Expenses (0/10)",
    "İLK VARLIĞINI EKLE": "ADD YOUR FIRST ASSET",
    "İÇE AKTAR": "IMPORT",
    "İçe aktarma sırasında hata oluştu!": "An error occurred during import!",
    "İçe aktarılıyor, lütfen bekleyin...": "Importing, please wait...",
    "İşlem başarıyla eklendi!": "Transaction added successfully!",
    "İşlem sırasında hata oluştu!": "An error occurred during the transaction!",
    "İşlem şifreleniyor...": "Encrypting transaction...",
    "⚠️ En fazla 3 aktif hedef ekleyebilirsin!": "⚠️ You can have up to 3 active goals!",
    "Toplam İşlem Kaydı": "Total Transactions",
    "Toplam Bütçe Kalemi": "Total Budget Items",
    "Dışa aktarıldı": "Exported",
    "Hata": "Error",
    "Taksit Sayısı": "Number of Installments",
    "için gereken süre": "Time required for",
    "Gün": "Days",
    "hedefi eklendi": "goal added",
    "eklendi": "added",
    "Para Yatır": "Deposit Funds",
    "Hedefi Sil": "Delete Goal",
    "Aylık:": "Monthly:",
    "Kalan": "Remaining",
    "bakiyeyi kapatmak istediğinize emin misiniz?": "Are you sure you want to pay off the remaining balance?",
    "Kaç taksit ödemek istiyorsunuz?": "How many installments would you like to pay?",
    "Maks": "Max",
    "Seçilen": "Selected",
    "Taksit": "Installment",
    "taksit başarıyla ödendi": "installments paid successfully",
    "Bakiye": "Balance",
    "Güncel Bakiye": "Current Balance",
    "Kullanılabilir Limit": "Available Limit",
    "Güncel Borç": "Current Debt",
    "Kart Kullanım Özeti": "Card Controls",
    "İnternet Alışverişi": "Online Shopping",
    "İnternet Alışverişi Tercihi": "Online Shopping Preference",
    "Yalnızca tercih olarak saklanır": "Stored as a preference only",
    "Bazı kayıtlar okunamadığı için gösterilemiyor": "Unavailable because some records could not be read",
    "Bu kart dondurulduğu için işlem yapılamaz. İşlem yapmak için önce kartın dondurmasını kaldırın.": "This card is frozen. Unfreeze it before making a transaction.",
    "Kartı Dondur": "Freeze Card",
    "Son Hareketler": "Recent Transactions",
    "Ekstre": "Statement",
    "Borç Öde": "Pay Debt",
    "BANKA KARTI": "DEBIT CARD",
    "Banka Kartı": "Debit Card",
    "SALT OKUNUR": "READ ONLY",
    "Gösterge hesabı • Harcama kaynağı değildir": "Display account • Cannot be used for spending",
    "Toplanan": "Saved",
    "Hedef": "Target",
    "Biriktir": "Save",
    "varlık • Son bilinen fiyat": "assets • Last known price",
    "varlık fiyatlandı": "assets priced",
    "TL dışı varlık • Canlı değer": "non-TRY assets • Live value",
    "Borç Ödeme": "Debt Payment",
    "ödendi": "paid",
    "kayıt dışa aktarıldı": "records exported",
    "Yatırım": "Investment",
    "Kazanç": "Earnings",
    "Seçtiğiniz kredi türü için vade en fazla": "The maximum term for the selected loan type is",
    "ay olabilir": "months",
    "PDF kaydedildi": "PDF saved",
    "Süre, kredi vadesinden büyük olamaz": "Duration cannot exceed the loan term",
    "Özel Masraflar": "Custom Expenses",
    "Net Getiri": "Net Return",
    "Vade Sonu": "Maturity Value",
    "%5 Stopaj düşülmüştür": "5% withholding tax deducted",
    "Aylık toplam": "Monthly total",
    "tutarında": "across",
    "olası abonelik bulundu": "potential subscriptions found",
    "kez": "times",
    "Kategori": "Category",
    "Son": "Last",
    "takibe alındı": "is now being tracked",
    "Bakiye Geçmişi (son": "Balance History (last",
    "gün)": "days)",
    "Bakiye defteri": "Balance ledger",
    "tarihinden itibaren kayıt tutuyor": "has records since",
    "Birikim hedeflerinde": "Savings goals",
    "değişim": "change",
    "Ayı Harcama Limitiniz": "Spending Limit",
    "Ekstre okunamadı": "Could not load statement",
    "Taksit planları kontrol edilemedi": "Could not check installment plans",
    "Kart silinemedi": "Could not delete card",
    "Taksit planları okunamadı": "Could not load installment plans",
    "Tür Seç": "Select Type",
    "Altın Türü": "Gold Type",
    "Yeni": "Add New",
    "Tür": "Type",
    "Alım": "Purchase",
    "Anlık": "Current",
    "Tasarruf oranı": "Savings rate",
    "Borç/gelir": "Debt/income",
    "Gider oynaklığı": "Expense volatility",
    "Çok İyi": "Excellent",
    "İyi": "Good",
    "Orta": "Fair",
    "Zayıf": "Poor",
    "Kritik": "Critical",
    "ayda": "per month",
    "/ ay": "/ month",
    "Hatalı kullanıcı adı veya şifre!": "Incorrect username or password!",
    "Hesap / Kart Adı": "Account / Card Name",
    "Başlangıç Bakiyesi (₺)": "Opening Balance (₺)",
    "Mevcut Borç (₺)": "Current Debt (₺)",
    "Toplam Limit (₺)": "Total Limit (₺)",
    "Hesap Kesim Günü (1-31, opsiyonel)": "Statement Day (1–31, optional)",
    "Kart Numarası (opsiyonel — kartsız hesap için boş bırakın)": "Card Number (optional — leave empty for an account without a card)",
    "Son Kullanma Tarihi (AA/YY)": "Expiry Date (MM/YY)",
    "CVC (Arkada yer alan 3 hane)": "CVC (3 digits on the back)",
    "Nakit / Vadesiz": "Cash / Checking",
    "Hesap / Kart Ekle": "Add Account / Card",
    "Miktar (₺)": "Amount (₺)",
    "Ödeme Yöntemi": "Payment Method",
    "Ödeme Adı (örn: Netflix)": "Payment Name (e.g. Netflix)",
    "GITHUB'DA AÇ": "OPEN ON GITHUB",
    "AKTAR VE SİL": "TRANSFER & DELETE",
    "Abonelik eklenemedi.": "Could not add the subscription.",
    "Bilimsel Hesap Makinesi": "Scientific Calculator",
    "Birikim Hedefi": "Savings Goal",
    "Borcu Kapat": "Pay Off Debt",
    "DEVAM": "CONTINUE",
    "Defter okunuyor...": "Loading ledger...",
    "EVET, KAPAT": "YES, PAY OFF",
    "Faiz Getirisi": "Interest Return",
    "Fiyat ve miktar zorunludur!": "Price and quantity are required!",
    "Geçerli bir fiyat girin!": "Enter a valid price!",
    "HEDEFE EKLE": "ADD TO GOALS",
    "HESABA AKTAR VE SİL": "REFUND & DELETE",
    "Hesaplama bekleniyor...": "Waiting for calculation...",
    "Kalem silindi.": "Item deleted.",
    "Bütçe kalemi eklendi!": "Budget item added!",
    "Bütçe kalemi güncellendi!": "Budget item updated!",
    "Planı Onayla": "Confirm Plan",
    "Bunu mevcut planınız olarak kullanmak ister misiniz?":
        "Do you want to use this as your current plan?",
    "ayının kalemleri Aralık'a kadar tüm aylara uygulanacak.":
        "items will be applied to every month through December.",
    "EVET, UYGULA": "YES, APPLY",
    "Bu planı yıl sonuna kadar uygula": "Apply this plan through year-end",
    "Plan uygulandı": "Plan applied",
    "kalem yıl sonuna kadar eklendi.": "items added through year-end.",
    "Plan zaten güncel; yeni kalem eklenmedi.":
        "Plan already up to date; no new items added.",
    "Plan uygulanırken bir hata oluştu.":
        "An error occurred while applying the plan.",
    "Kart Ekstresi": "Card Statement",
    "Kredi Hesaplama": "Loan Calculator",
    "Maksimum 10 masraf ekleyebilirsiniz.": "You can add up to 10 custom expenses.",
    "Miktar": "Quantity",
    "Miktar (adet)": "Quantity (units)",
    "Miktar / Lot (adet)": "Quantity / Lots",
    "SAT": "SELL",
    "SIFIRLA": "RESET",
    "Sembol, fiyat ve miktar zorunludur!": "Symbol, price, and quantity are required!",
    "TABLO": "SCHEDULE",
    "Tek Seferlik": "One-time",
    "Vade (Ay - Maks 36)": "Term (Months — Max 36)",
    "YATIR": "DEPOSIT",
    "Varlık fiyatları hesaplanıyor...": "Calculating asset prices...",
    "Kullanılabilir hesap yok": "No available accounts",
    "Ödeme Yöntemi (hesap yok)": "Payment Method (no accounts)",
    "Vade (Ay - Maks 48)": "Term (Months — Max 48)",
    "Vade (Ay - Maks 120)": "Term (Months — Max 120)",
    "Bağlantı Hatası!": "Connection Error!",
    "Canlı veri bekleniyor…": "Waiting for live data…",
    "Hesaplanamadı": "Could Not Calculate",
    "Canlı fiyatlara ulaşılamadı": "Live prices are unavailable",
    "Fiyatlar alınamadı": "Prices could not be fetched",
    "Veri Yok": "No Data",
    "₺0\nVeri Yok": "₺0\nNo Data",
    "Yatırım[/color]": "Investment[/color]",
    "Satış[/color]": "Sale[/color]",
    "ODE Simülasyonu: Mevcut ivme ve %3,65 yıllık parametre ile": "ODE Simulation: With the current momentum and a 3.65% annual parameter,",
    "30 gün sonraki beklenen varlık": "expected wealth in 30 days",
    "Dikkat: ODE modeli varlığınızın eksiye düşeceğini gösteriyor. Harcamalarınızı acilen gözden geçirin!": "Warning: The ODE model projects negative wealth. Review your spending immediately!",
    "Gider ivmeniz gelirinizi aşıyor; varlığınız": "Your expense momentum exceeds your income; your wealth may decrease by",
    "azalabilir": "",
    "Mevcut gelir-gider dengesiyle varlığınız": "With your current income-expense balance, your wealth may increase by",
    "artış gösterebilir": "",
    "Bu ay harcamalarınız geçen döneme kıyasla": "Compared with the previous period, your spending this month",
    "En çok harcama yapılan alan": "Highest-spending category",
    "Bu ayki net tasarruf oranınız": "Your net savings rate this month",
    "Harika birikim dönemi!": "A strong month for saving!",
    "Yok": "None",
    "Kategori ara...": "Search categories...",
    "Bu kategorideki ortalamanın": "Above this category's average by",
    "üzerinde": "",
    "Ana Gelir": "Primary Income",
    "Ek Gelir": "Additional Income",
    "Temel Gider": "Essential Expenses",
    "Ekstra Gider": "Discretionary Expenses",
    "Açılış Bakiyesi": "Opening Balance",
    "Maaş": "Salary", "Avans": "Advance", "Prim": "Bonus", "Mesai": "Overtime",
    "Kıdem Tazminatı": "Severance Pay", "İhbar Tazminatı": "Notice Pay",
    "Danışmanlık": "Consulting", "Proje Bedeli": "Project Income", "Ürün Satışı": "Product Sales",
    "E-Ticaret": "E-Commerce", "Hak Ediş": "Progress Payment", "Ev Kirası (Gelir)": "Rental Income",
    "Dükkan Kirası": "Commercial Rent", "Araç Kirası": "Vehicle Rental Income",
    "Temettü": "Dividends", "Kripto Kazancı": "Crypto Gains", "Fon Getirisi": "Fund Returns",
    "Kupon Ödemesi": "Coupon Payment", "Emekli Maaşı": "Pension", "İşsizlik Maaşı": "Unemployment Benefit",
    "Çocuk Yardımı": "Child Benefit", "Burs": "Scholarship", "Nafaka": "Alimony",
    "Devlet Teşviki": "Government Grant", "Piyango/Loto": "Lottery", "Miras": "Inheritance",
    "Borç Tahsilatı": "Debt Collection", "Nakit Hediye": "Cash Gift", "İade": "Refund",
    "Varlık Satışı": "Asset Sale", "Ev Kirası": "Rent", "Aidat": "Maintenance Fee",
    "Emlak Vergisi": "Property Tax", "Ev Bakım/Onarım": "Home Maintenance", "Ev Eşyası": "Household Items",
    "Elektrik": "Electricity", "Su": "Water", "Doğalgaz": "Natural Gas", "İnternet": "Internet",
    "Cep Telefonu": "Mobile Phone", "Dijital Platformlar": "Streaming Services",
    "Dijital Abonelik": "Digital Subscription",
    "Akaryakıt": "Fuel", "Toplu Taşıma": "Public Transport", "Taksi": "Taxi",
    "Araç Bakım": "Vehicle Maintenance", "MTV": "Motor Vehicle Tax", "Sigorta/Kasko": "Insurance",
    "Otopark/Köprü": "Parking/Tolls", "Süpermarket": "Groceries", "Pazaryeri": "Marketplace",
    "Dışarıda Yemek": "Dining Out", "Paket Servis": "Food Delivery", "Su Siparişi": "Water Delivery",
    "Hastane": "Hospital", "İlaç/Eczane": "Pharmacy", "Sağlık Sigortası": "Health Insurance",
    "Kişisel Bakım": "Personal Care", "Kuaför/Berber": "Hairdresser/Barber", "Spor Salonu": "Gym",
    "Okul/Kurs": "School/Courses", "Kitap/Kırtasiye": "Books/Stationery", "Sınav Ücretleri": "Exam Fees",
    "Sinema/Tiyatro": "Cinema/Theatre", "Oyun/Uygulama": "Games/Apps", "Tatil/Konaklama": "Travel/Accommodation",
    "Hobiler": "Hobbies", "Kıyafet": "Clothing", "Ayakkabı": "Shoes", "Çanta": "Bags",
    "Takı/Aksesuar": "Jewelry/Accessories", "Kredi Taksiti": "Loan Installment", "Borç Ödeme": "Debt Payment",
    "Vergi Ödemeleri": "Tax Payments", "Bağış/Zekat": "Donations/Zakat", "Çocuk Bakımı": "Childcare",
    "Evcil Hayvan": "Pets", "Varlık Alımı": "Asset Purchase",
    "arttı": "increased",
    "azaldı": "decreased",
    "karşılaştırılacak veri yok": "no comparison data",
    "Bütçeniz dengede.": "Your budget is balanced.",
    "Dikkat: Planlanan giderler, gelirlerinizi aşıyor. Bütçeniz eksiye düşecek!": "Warning: Planned expenses exceed your income. Your budget will run a deficit!",
    "Dikkat: Gelir ve gideriniz başa baş. Bütçenizde hiç esneme payı yok.": "Warning: Your income and expenses break even. Your budget has no buffer.",
    "Geçersiz tutar": "Invalid amount",

    # --- İşlem tarihi seçici (ileri/geçmiş tarihli işlem) ---
    "Tarih: Bugün": "Date: Today",
    "Tarih:": "Date:",
    "Bu işlem bekleyenler listesine eklenecek; tarihi geldiğinde bakiyeye yansıyacak.": "This transaction goes to the pending list and will hit your balance on its date.",
    "İşlem": "Transaction",
    "tarihine planlandı; bekleyenler listesinde.": "— scheduled; it is in the pending list.",

    # --- Bekleyen (ileri tarihli) işlemler paneli ---
    "Bekleyen İşlemler": "Pending Transactions",
    "BEKLEYENLERİ YÖNET": "MANAGE PENDING",
    "Bekleyen işlem bulunmuyor.": "No pending transactions.",
    "Bekleyen işlemler okunamadı.": "Could not load pending transactions.",
    "Bekleyen işlem iptal edilemedi.": "Could not cancel the pending transaction.",
    "Bekleyen işlem ertelenemedi.": "Could not reschedule the pending transaction.",
    "Bu işlem artık bekleyen durumda değil.": "This transaction is no longer pending.",
    "ERTELE": "RESCHEDULE",
    "işlem bakiyenize henüz yansımadı.": "transaction(s) have not hit your balance yet.",
    "Beklenen gelir:": "Expected income:",
    "Beklenen gider:": "Expected expense:",
    "En yakın tarih:": "Next date:",
    "Planlanan:": "Scheduled:",
    "bugün işlenecek": "posts today",
    "yarın işlenecek": "posts tomorrow",
    "gün sonra": "days from now",
    "iptal edildi.": "cancelled.",
    "bakiyenize işlendi.": "posted to your balance.",
    "Yeni tarih:": "New date:",

    # --- Abonelik yönetimi (iptal / iade / zam) ---
    "Aboneliklerim": "My Subscriptions",
    "Aboneliği Kaldır": "Remove Subscription",
    "DÜZENLE": "EDIT",
    "KALDIR": "REMOVE",
    "SADECE BU AY": "THIS MONTH ONLY",
    "KALICI OLARAK": "PERMANENTLY",
    "Ücret İadesi": "Refund",
    "EVET, İADE ET": "YES, REFUND",
    "HAYIR, GEREK YOK": "NO, THANKS",
    "Yeni Aylık Ücret (₺)": "New Monthly Price (₺)",
    "Abonelikler okunamadı.": "Could not load subscriptions.",
    "Abonelik ücreti güncellenemedi.": "Could not update the subscription price.",
    "Abonelik kaldırılamadı.": "Could not remove the subscription.",
    "aboneliğini nasıl kaldırmak istersiniz?": "— how would you like to remove it?",
    "Ücreti Güncelle": "Update Price",
    "ücreti güncellendi.": "price updated.",
    "aboneliği durduruldu.": "subscription stopped.",
    "bu ay için atlandı.": "skipped for this month.",
    "bakiyenize eklendi.": "was added back to your balance.",
    "Bu ay": "This month",
    "için": "for",
    "kesilmiş. Bu tutarı bakiyenize geri eklemek ister misiniz?": "was charged. Would you like it added back to your balance?",
    "Sonraki:": "Next:",
    "Skor hesaplamak için henüz yeterli veri yok. ": "Not enough data yet to compute a score. ",

    # --- Onboarding: zorunlu ilk hesap oluşturma ekranı ---
    "İlk Hesabını Oluştur": "Create Your First Account",
    "Gelir ve giderlerin bir hesaba işlenmesi gerekir. Dilediğin zaman Kartlarım sekmesinden yeni hesap veya kart ekleyebilirsin.": "Income and expenses must post to an account. You can add more accounts or cards any time from the My Cards tab.",
    "Hesap Adı (Örn: Nakit Cüzdanım)": "Account Name (e.g. My Cash Wallet)",
    "Nakit Cüzdanım": "My Cash Wallet",
    "HESABI OLUŞTUR": "CREATE ACCOUNT",

    # --- 2026-07-23: çeviri katmanından geçmeyen dizeler taraması ---
    "Anapara": "Principal",
    "Ay": "Month",
    "Ek Masraf": "Extra Cost",
    "Faiz/Vergi": "Interest/Tax",
    "Toplam Ödeme": "Total Payment",
    "Temel Taksit": "Base Installment",
    "Toplam Geri Ödeme": "Total Repayment",
    "Ele Geçecek": "Net Disbursed",
    "Tüm Peşin Masraflar Düşülmüş": "All upfront costs deducted",
    "--- TEK SEFERLİK (PEŞİN) MASRAFLAR DETAYI ---": "--- ONE-TIME (UPFRONT) COSTS DETAIL ---",
    "Kredi Tahsis Ücreti": "Loan Origination Fee",
    "Hayat Sigortası (Ortalama)": "Life Insurance (Average)",
    "Toplam Peşin Kesinti": "Total Upfront Deduction",
    "Krediden Ele Geçecek Net Tutar": "Net Amount Disbursed From Loan",
    "Yatırılacak Tutar (₺)": "Amount to Deposit (₺)",
    "Şu anki hızla ~": "At the current pace, ~",
    " ay kaldı": " months left",
    "🎉🎉🎉 Hedefe ulaştın!": "🎉🎉🎉 You reached your goal!",
    "tamamlandı!": "complete!",
    "Bu hedef için şu ana kadar biriktirdiğiniz ": "So far you've saved ",
    " ₺ ne yapılsın?": " ₺ toward this goal — what should we do?",
    "Bu hedefte birikmiş bakiye yok. Hedef kalıcı olarak silinsin mi?": "This goal has no saved balance. Delete it permanently?",
    "Hedef bulunamadı": "Goal not found",
    "Bakiyenin aktarılacağı hesap seçilmelidir": "You must select an account to receive the balance",
    "Seçilen vadesiz hesap bulunamadı": "The selected checking account was not found",
    "Bakiye hesaba aktarıldı ve hedef silindi.": "Balance transferred to the account and the goal was deleted.",
    "Hedef silindi.": "Goal deleted.",
    "Güncel Limit": "Current Limit",
    "Tebrikler, hedefe ulaştın! 🎉": "Congratulations, you reached your goal! 🎉",
    "Henüz tahmin için yeterli veri yok": "Not enough data yet for an estimate",
    "Ödeme yöntemi seçilmedi": "No payment method selected",
    "Dikkat: Bu karta ait devam eden ": "Warning: This card has ",
    " adet aktif taksit planı": " active installment plan(s)",
    " bulunmaktadır. Kartı sildiğinizde bu taksit planları ve tüm geçmiş işlemler de kalıcı olarak silinecektir. Onaylıyor musunuz?": ". Deleting the card will permanently remove these plans and all related past transactions. Continue?",
    " kartı, karta bağlı tüm geçmiş işlemler ve otomatik ödemeler kalıcı olarak silinecektir. Onaylıyor musunuz?": " card — all related past transactions and auto-payments will be permanently deleted. Continue?",
    "Kartı Sil": "Delete Card",
    " Taksit Ödendi": " Installments Paid",
    "Hesap adı boş olamaz.": "Account name cannot be empty.",
    "Bilinmeyen hesap türü: ": "Unknown account type: ",
    "Tutar ve limit sayısal olmalıdır.": "Amount and limit must be numeric.",
    "Hesap kesim günü 1-31 arası bir sayı olmalıdır.": "The statement day must be a number between 1 and 31.",
    "Hesap kesim günü 1-31 arası olmalıdır.": "The statement day must be between 1 and 31.",
    "Kredi kartı için 0'dan büyük bir limit girilmelidir.": "A limit greater than zero must be entered for a credit card.",
    "Mevcut borç negatif olamaz.": "The current debt cannot be negative.",
    "Mevcut borç, kart limitini aşamaz.": "The current debt cannot exceed the card limit.",
    "İşlem kaydedilirken bir hata oluştu!": "An error occurred while saving the transaction!",
    "Aktif Varlık hesabı salt okunurdur ve harcama kaynağı olamaz.": "The Active Assets account is read-only and cannot be used as a spending source.",
    "Taksit sayısı 1 ile 12 arasında olmalıdır.": "The number of installments must be between 1 and 12.",
    "Hesap bulunamadı.": "Account not found.",
    "Yetersiz Bakiye! Bu hesap eksiye düşemez.": "Insufficient balance! This account cannot go negative.",
    "Limit yetersiz: kullanılabilir limit ": "Insufficient limit: available limit ",
    ", harcama ": ", spending ",
    "Ayın ": "Day ",
    ". günü otomatik ödenecek": " of each month (auto-pay)",
    "Tamamen Kapat": "Pay Off Completely",
    "Ödeme Günü (1-31)": "Payment Day (1-31)",
    "Ödenecek tutar sıfırdan büyük olmalıdır.": "The payment amount must be greater than zero.",
    "Geçersiz kredi kartı.": "Invalid credit card.",
    "Bu kredi kartında ödenecek borç bulunmuyor.": "There is no outstanding debt on this credit card.",
    "Ödeme yapılacak hesap vadesiz hesap olmalıdır.": "The payment account must be a checking account.",
    "Ödeme mevcut kart borcunu aşamaz.": "The payment cannot exceed the current card debt.",
    "Bakiye defteri ": "Balance ledger ",
    " tarihinde başlıyor; öncesi için kayıt yok.\n": " is when it starts; there are no records before that date.\n",
    "Aşağıdaki hareketler defterin başlangıcından bugüne.": "The entries below span from the ledger's start to today.",
    "Gelir/gider işlemleri": "Income/expense transactions",
    "Birikime aktarım": "Transferred to savings",
    "Birikimden iade": "Refunded from savings",
    "Hedef silme iadesi": "Goal deletion refund",
    "Hedef açılışı": "Goal created",
    "Hesap açılışı": "Account opened",
    "Sistem sıfırlama": "System reset",
    "Tüm veri silme": "All data deleted",
    "haftalık": "weekly",
    "iki haftada bir": "biweekly",
    "aylık": "monthly",
    "üç ayda bir": "quarterly",
    "yıllık": "yearly",
    "Pazartesi": "Monday", "Salı": "Tuesday", "Çarşamba": "Wednesday",
    "Perşembe": "Thursday", "Cuma": "Friday", "Cumartesi": "Saturday",
    "Pazar": "Sunday",
    "Finansal sağlık raporu şu anda oluşturulamadı. Ana sayfayı yenileyerek tekrar deneyebilirsin.": "The financial health report could not be generated right now. You can refresh the home page to try again.",
    "K/Z: ": "P/L: ",
    "alındı": "purchased",
    "satıldı": "sold",
    "adet, birim fiyat": "units, unit price",
    "Gram Altın": "Gram Gold",
    "Ons Altın": "Ounce Gold",
    "Çeyrek Altın": "Quarter Gold",
    "Yarım Altın": "Half Gold",
    "Tam Altın": "Full Gold",
    "Dolar": "Dollar",
    "Sembol (Otomatik: GC=F)": "Symbol (Auto: GC=F)",
    "Sembol (Örn: BTC-USD)": "Symbol (e.g. BTC-USD)",
    "Sembol (Örn: USDTRY=X)": "Symbol (e.g. USDTRY=X)",
    "Sembol": "Symbol",
    "Yukarıdan tür seçin veya elle girin (Gram: GC=F)": "Select a type above or enter manually (Gram: GC=F)",
    "Yahoo Finance sembolü girin": "Enter the Yahoo Finance symbol",
    "Hisse": "Stock",
    # Varlık türü listesinde uzun yazımı da geçiyor; kısa anahtarın
    # alt dize olarak eşleşmesine güvenmek "Stock Senedi" gibi yarı
    # çevrilmiş melezler üretiyordu.
    "Hisse Senedi": "Stock",
    "Altın": "Gold",
    "Tahvil": "Bond",
    "Döviz": "Currency",
    "Kripto": "Crypto",
    "Diğer": "Other",
    "Miktar: ": "Quantity: ",
    "Alım fiyatı: ": "Purchase price: ",
    "Satış tamamlandı! ": "Sale completed! ",
    "Ocak": "January",
    "Şubat": "February",
    "Mart": "March",
    "Nisan": "April",
    "Mayıs": "May",
    "Haziran": "June",
    "Temmuz": "July",
    "Ağustos": "August",
    "Eylül": "September",
    "Ekim": "October",
    "Kasım": "November",
    "Aralık": "December",

    # ── Şablona PARAMETRE olarak giren kontrollü etiketler ───────────────
    #
    # Bunlar kullanıcı verisi DEĞİL, uygulamanın kendi sözlüğü. Şablonun
    # içine girmeden ÖNCE `tr()` ile ayrıca çevrilirler; karşılıkları
    # burada olmazsa İngilizce cümlenin ortasında Türkçe bir parça kalır
    # ("Balance on 2026-08-01 · Günlük snapshot" gibi).
    "Gelir işlemleri": "Income transactions",
    "Gider işlemleri": "Expense transactions",
    "Günlük snapshot": "Daily snapshot",
    "Defter replay": "Ledger replay",
    # `_secure_operation_error` çağrı yerlerinden gelen sabit başlıklar.
    "Backup oluşturulamadı": "Backup could not be created",
    "Restore başarısız; mevcut veri korundu":
        "Restore failed; your current data was preserved",
    "Migration geri alındı": "Migration was rolled back",
    "Kurtarma paketi oluşturulamadı":
        "Recovery package could not be created",
    "Kurtarma paketi içe aktarılamadı":
        "Recovery package could not be imported",
    "Anahtar rotasyonu başlatılamadı": "Key rotation could not be started",
    "Anahtar rotasyonu geri alındı": "Key rotation was rolled back",
    # Tekrarlayan işlem diyaloğunun sabit soru/açıklama çiftleri.
    "Bu ayki gelir hesaba eklensin mi?":
        "Should this month's income be added to the account?",
    "Bu ayki gider hesaptan düşülsün mü?":
        "Should this month's expense be deducted from the account?",
    "“BU AYI DAHİL ET” seçilirse bu ayın günü geçtiyse gelir hemen, "
    "gelmediyse seçilen günde eklenir.":
        "If “INCLUDE THIS MONTH” is selected, the income is added right away "
        "when this month's day has passed, and on the selected day otherwise.",
    "“BU AYI DAHİL ET” seçilirse bu ayın günü geçtiyse gider hemen, "
    "gelmediyse seçilen günde düşülür.":
        "If “INCLUDE THIS MONTH” is selected, the expense is deducted right "
        "away when this month's day has passed, and on the selected day "
        "otherwise.",

# ─── Şablonlar (`trf`) ────────────────────────────────────────────────────
#
# Bu bölümdeki anahtarlar YER TUTUCU içerir ve yalnız `trf()` ile kullanılır:
# önce şablon çevrilir, sonra parametreler yerleştirilir. Parametre değerleri
# (hesap adı, hedef adı, tutar, tarih) çeviriden GEÇMEZ.
#
# Yer tutucu KÜMESİ iki dilde aynı olmak zorundadır; SIRA serbesttir ve
# İngilizce cümle yapısı bunu zaten gerektirir:
#     "{name} hesabı eklendi."  ->  "Account added: {name}"
# `tests/test_i18n_static_gate.py` kümelerin eşitliğini kapıya bağlıyor.

    "\nEle Geçecek: {net} (Tüm Peşin Masraflar Düşülmüş)":
        "\nNet Proceeds: {net} (All upfront costs deducted)",
    "   •  Ayın {auto_pay_day}. günü otomatik ödenecek":
        "   •  Auto-paid on day {auto_pay_day} of the month",
    " {amount} bakiyenize eklendi.":
        " {amount} was added to your balance.",
    "%{percent} arttı": "up %{percent}",
    "%{percent} azaldı": "down %{percent}",
    "'{name}' için gereken süre:\n{periods} Ay\n(~{approx})":
        "Time needed for '{name}':\n{periods} months\n(~{approx})",
    "'{name}' için gereken süre:\n{periods} Gün\n(~{approx})":
        "Time needed for '{name}':\n{periods} days\n(~{approx})",
    "Altın Türü: {label}": "Gold Type: {label}",
    "Alım: {purchase_price} ₺  ×  {quantity}":
        "Purchase: {purchase_price} ₺  ×  {quantity}",
    "Anahtar rotasyonu tamamlandı: {rotated_fields} alan. Backup: {backup_path}":
        "Key rotation complete: {rotated_fields} fields. Backup: {backup_path}",
    "Anlık: {current_price} ₺": "Live: {current_price} ₺",
    "Aylık toplam {amount} tutarında {count} olası abonelik bulundu.":
        "Found {count} possible subscriptions totalling {amount} per month.",
    "Aylık: {monthly_payment} ₺": "Monthly: {monthly_payment} ₺",
    "Backup doğrulandı:\n{path}": "Backup verified:\n{path}",
    "Bakiye Geçmişi (son {days_back} gün)":
        "Balance History (last {days_back} days)",
    "Bakiye Geçmişi ({from_date} → {to_date})":
        "Balance History ({from_date} → {to_date})",
    "Bakiye defteri {value} tarihinde başlıyor; {date} için kayıt yok.":
        "The balance ledger starts on {value}; there is no record for {date}.",
    "Bakiye defteri {value} tarihinde başlıyor; öncesi için kayıt yok.\n"
    "Aşağıdaki hareketler defterin başlangıcından bugüne.":
        "The balance ledger starts on {value}; there is no record before that.\n"
        "The movements below run from the start of the ledger to today.",
    "Beklenen gelir: {amount}": "Expected income: {amount}",
    "Beklenen gider: {amount}": "Expected expense: {amount}",
    "Birikim hedeflerinde: {amount} değişim":
        "Change in savings goals: {amount}",
    "Bu ay harcamalarınız geçen döneme kıyasla {change_text}.\n"
    "En çok harcama yapılan alan: {highest_cat_name}.\n"
    "Bu ayki net tasarruf oranınız: %{savings_rate}. Harika birikim dönemi!":
        "Your spending this month is {change_text} compared with the previous "
        "period.\nHighest spending area: {highest_cat_name}.\n"
        "Your net savings rate this month: %{savings_rate}. Great going!",
    "Bu ay {name} için {amount} kesilmiş. "
    "Bu tutarı bakiyenize geri eklemek ister misiniz?":
        "{amount} was charged for {name} this month. "
        "Would you like to add it back to your balance?",
    "Bu hedef için şu ana kadar biriktirdiğiniz {amount} ₺ ne yapılsın?":
        "What should happen to the {amount} ₺ you have saved for this goal?",
    "Dikkat: Bu karta ait devam eden [b]{count} adet aktif taksit planı[/b] "
    "bulunmaktadır. Kartı sildiğinizde bu taksit planları ve tüm geçmiş "
    "işlemler de kalıcı olarak silinecektir. Onaylıyor musunuz?":
        "Warning: this card has [b]{count} active instalment plan(s)[/b]. "
        "Deleting the card permanently deletes those plans and all past "
        "transactions as well. Do you confirm?",
    "Ekstre okunamadı: {detail}": "Could not read the statement: {detail}",
    "En yakın tarih: {nearest}": "Nearest date: {nearest}",
    "Gecikti ({days} gün)": "Overdue ({days} days)",
    "Hata: {error_msg}": "Error: {error_msg}",
    "Hedefi Sil: {name}": "Delete Goal: {name}",
    "Hesap eklendi: {name}": "Account added: {name}",
    "Hesap: {name}": "Account: {name}",
    "K/Z: {sign}{amount}": "P/L: {sign}{amount}",
    "Kalan {remaining_balance} ₺ bakiyeyi kapatmak istediğinize emin misiniz?":
        "Are you sure you want to clear the remaining {remaining_balance} ₺?",
    "Kalan: {amount}": "Remaining: {amount}",
    "Kalan: {count} Taksit": "Remaining: {count} instalments",
    "Kalan: {remaining}/{total} Taksit":
        "Remaining: {remaining}/{total} instalments",
    "Kart silinemedi: {detail}": "Could not delete the card: {detail}",
    "Kaç taksit ödemek istiyorsunuz? (Maks: {remaining_installments})":
        "How many instalments do you want to pay? (Max: {remaining_installments})",
    "Kurtarma paketi doğrulandı:\n{path}": "Recovery package verified:\n{path}",
    "Migration tamamlandı: {migrated_fields} alan. Backup: {backup_path}":
        "Migration complete: {migrated_fields} fields. Backup: {backup_path}",
    "Net Getiri: + {profit}\nVade Sonu: {total}\n(%5 Stopaj düşülmüştür)":
        "Net Return: + {profit}\nAt Maturity: {total}\n(5% withholding deducted)",
    "PDF kaydedildi: {filepath}": "PDF saved: {filepath}",
    "Restore tamamlandı. Güvenlik backup'ı:\n{safety_backup_path}":
        "Restore complete. Safety backup:\n{safety_backup_path}",
    "Satış tamamlandı! {sign}₺{value} K/Z":
        "Sale completed! {sign}₺{value} P/L",
    "Seçilen: {count} Taksit": "Selected: {count} instalments",
    "Seçtiğiniz kredi türü için vade en fazla {max_term} ay olabilir!":
        "For the selected loan type the term can be at most {max_term} months!",
    "Süre, kredi vadesinden büyük olamaz ({term} ay)!":
        "The period cannot exceed the loan term ({term} months)!",
    "Taksit Sayısı: {count}": "Number of Instalments: {count}",
    "Taksit Sayısı: {selected_installments}":
        "Number of Instalments: {selected_installments}",
    "Taksit planları kontrol edilemedi: {detail}":
        "Could not check the instalment plans: {detail}",
    "Taksit planları okunamadı: {detail}":
        "Could not read the instalment plans: {detail}",
    "Tarih: {date}": "Date: {date}",
    "Tasarruf oranı %{savings}  ·  Borç/gelir %{debt}  ·  "
    "Gider oynaklığı %{volatility}":
        "Savings rate %{savings}  ·  Debt/income %{debt}  ·  "
        "Spending volatility %{volatility}",
    "Temel Taksit: {monthly}\nToplam Geri Ödeme: {total}":
        "Base Instalment: {monthly}\nTotal Repayment: {total}",
    "Tür Seç: {asset_selected_type}": "Select Type: {asset_selected_type}",
    "Tür Seç: {asset_type}": "Select Type: {asset_type}",
    "Tür Seç: {type}": "Select Type: {type}",
    "Tür: {asset_type}": "Type: {asset_type}",
    "Yatırım: {invested}\nKazanç: + {profit}\nToplam: {amount}":
        "Invested: {invested}\nGain: + {profit}\nTotal: {amount}",
    "Yeni tarih: {new_date}": "New date: {new_date}",
    "Yeni {asset_selected_type} Ekle": "Add New {asset_selected_type}",
    "[color=#0277BD]- ₺{amount} Yatırım[/color]":
        "[color=#0277BD]- ₺{amount} Deposit[/color]",
    "[color=#2E7D32]+ ₺{amount} Satış[/color]":
        "[color=#2E7D32]+ ₺{amount} Sale[/color]",
    "{amount} / ay": "{amount} / month",
    "{amount} × {occurrences} kez  →  ayda {amount_1}\n"
    "Kategori: {category}  ·  Son: {last_seen}":
        "{amount} × {occurrences} times  →  {amount_1} per month\n"
        "Category: {category}  ·  Last: {last_seen}",
    "{asset_name} ({asset_code})\n"
    "Miktar: {quantity}  |  Alım fiyatı: {purchase_price} ₺":
        "{asset_name} ({asset_code})\n"
        "Quantity: {quantity}  |  Purchase price: {purchase_price} ₺",
    "{a} · {b} · {c}": "{a} · {b} · {c}",
    "{category} · {amount}\n"
    "Bu kategorideki ortalamanın {amount_1} üzerinde ({date})":
        "{category} · {amount}\n"
        "{amount_1} above the average for this category ({date})",
    "{count} TL dışı varlık • Canlı değer":
        "{count} non-TRY assets • Live value",
    "{count} Taksit": "{count} instalments",
    "{count} işlem bakiyenize henüz yansımadı.":
        "{count} transactions have not reached your balance yet.",
    "{count} kayıt dışa aktarıldı:\n{path}":
        "{count} records exported:\n{path}",
    "{date} gün sonu\nBirikim hedefleri: {amount}\nKaynak: {value}":
        "End of day {date}\nSavings goals: {amount}\nSource: {value}",
    "{date} işlemleri yükleniyor...":
        "Loading transactions for {date}...",
    "{date} — {count} işlem": "{date} — {count} transactions",
    "{date}: işlem yok.": "{date}: no transactions.",
    "{date}: işlemler okunamadı.":
        "{date}: transactions could not be read.",
    "{days_left} gün kaldı": "{days_left} days left",
    "{days} Gün": "{days} days",
    "{debt_name} — Otomatik Ödeme": "{debt_name} — Automatic Payment",
    "{description}\n{signed_amount}  ·  Planlanan: {execution_date}  ·  {timing}":
        "{description}\n{signed_amount}  ·  Scheduled: {execution_date}  ·  {timing}",
    "{description} bakiyenize işlendi.":
        "{description} was applied to your balance.",
    "{description} iptal edildi.": "{description} was cancelled.",
    "{legacy_fields} alan / {affected_records} kayıt taşınacak. "
    "Önce doğrulanmış backup alınır; hata olursa transaction geri alınır.":
        "{legacy_fields} fields / {affected_records} records will be migrated. "
        "A verified backup is taken first; on error the transaction is rolled back.",
    "{message}. Ayrıntılar uygulama loguna kaydedildi.":
        "{message}. Details were written to the application log.",
    "{months} Ay": "{months} months",
    "{months} Ay, {days} Gün": "{months} months, {days} days",
    "{month} {year}": "{month} {year}",
    "{name}\n{amount}  ·  Sonraki: {due}":
        "{name}\n{amount}  ·  Next: {due}",
    "{name}  ·  {frequency}": "{name}  ·  {frequency}",
    "{name} (Bakiye: {balance} ₺)": "{name} (Balance: {balance} ₺)",
    "{name} Borç Ödeme": "{name} Debt Payment",
    "{name} aboneliği durduruldu.": "{name} subscription stopped.",
    "{name} aboneliğini nasıl kaldırmak istersiniz?":
        "How would you like to remove the {name} subscription?",
    "{name} bu ay için atlandı.": "{name} was skipped for this month.",
    "{name} eklendi": "{name} added",
    "{name} kartı, karta bağlı tüm geçmiş işlemler ve otomatik ödemeler "
    "kalıcı olarak silinecektir. Onaylıyor musunuz?":
        "The card {name}, along with every past transaction and automatic "
        "payment linked to it, will be permanently deleted. Do you confirm?",
    "{name} takibe alındı.": "{name} is now being tracked.",
    "{name} ücreti güncellendi.": "The price of {name} was updated.",
    "{name} — Para Yatır": "{name} — Deposit",
    "{name} — Ücreti Güncelle": "{name} — Update Price",
    "{name} → {name}": "{name} → {name}",
    "{paid}/{total} Taksit Ödendi": "{paid}/{total} instalments paid",
    "{priced}/{total} varlık fiyatlandı": "{priced}/{total} assets priced",
    "{priced}/{total} varlık • Son bilinen fiyat":
        "{priced}/{total} assets • Last known price",
    "{question}\n\n{detail}": "{question}\n\n{detail}",
    "{remaining} gün sonra": "in {remaining} days",
    "{selected_date} Tarihindeki Bakiye": "Balance on {selected_date}",
    "{selected_installments} taksit başarıyla ödendi!":
        "{selected_installments} instalments paid successfully!",
    "{sign}{pnl_pct}%  |  {sign}{pnl_amount} ₺  (Toplam: {total_value} ₺)":
        "{sign}{pnl_pct}%  |  {sign}{pnl_amount} ₺  (Total: {total_value} ₺)",
    "{sign}{value} ({c_sign}{value_1}%) Bugün":
        "{sign}{value} ({c_sign}{value_1}%) Today",
    "{source} ({count})": "{source} ({count})",
    "{time}  {category}": "{time}  {category}",
    "{years} Yıl, {months} Ay": "{years} years, {months} months",
    "Çok fazla hatalı deneme. {seconds} saniye sonra tekrar deneyin.":
        "Too many failed attempts. Try again in {seconds} seconds.",
    "Özel Masraflar ({count}/10)": "Custom Costs ({count}/10)",
    "İşlem {date} tarihine planlandı; bekleyenler listesinde.":
        "The transaction was scheduled for {date}; it is in the pending list.",
    "Şu anki hızla ~{months} ay kaldı":
        "~{months} months left at the current pace",
    "…ve {count} kayıt daha.": "…and {count} more records.",
    "₺{amount} eklendi!": "₺{amount} added!",
    "✔ '{name}' hedefi eklendi!": "✔ Goal '{name}' added!",
    "✔ {label} eklendi: {name}": "✔ {label} added: {name}",
    "🎉 %{percent} tamamlandı!": "🎉 %{percent} complete!",
}

# Bu iki kaynak anahtar, tarihsel olarak çağrı noktalarında İngilizce tutuluyor.
# KV/Python literal eşleşmesini bozmadan Türkçe arayüzde gerçek karşılıklarını
# göstermek için dar kapsamlı bir kaynak-dil override tablosu kullanılır.
TR = {
    "What-If\nSandbox": "Varsayım\nAlanı",
    "What-If Sandbox": "Varsayım Alanı",
}


def set_language(code):
    """Aktif dili ayarlar ve normalize edilmiş kodu döndürür."""
    global _language
    _language = code if code in SUPPORTED_LANGUAGES else "tr"
    return _language


def get_language():
    return _language


def tr(text: str | None, language: str | None = None) -> str:
    """Metni istenen dile çevirir — YALNIZ TAM EŞLEŞME ile.

    Bilinmeyen metinde kaynağa geri döner. Alt dize değiştiren "yaklaşık
    çeviri" KALDIRILDI: kullanıcının kendi verisini (hesap/hedef/abonelik adı,
    işlem açıklaması) sessizce değiştiriyor ve cümleleri yarı çevrilmiş
    melezlere dönüştürüyordu. Dinamik cümleler için `trf()` kullanılır.
    """
    if text is None:
        return ""
    code = language if language in SUPPORTED_LANGUAGES else _language
    source = text
    if code != "en":
        return TR.get(source, source)
    return EN.get(source, source)


#: ŞABLONA GİRMEDEN ÖNCE `tr()`DEN GEÇMESİ ZORUNLU etiket kaynakları.
#:
#: `trf()` parametreleri üç sınıfa ayrılır (docs/ARCHITECTURE.md):
#:   * kullanıcı verisi — ASLA çevrilmez,
#:   * sayı/tarih/tutar/yol/hata ayrıntısı — biçimlenir ama çevrilmez,
#:   * kontrollü etiket — tam anahtarla AYRICA çevrilir.
#:
#: Üçüncü sınıfı otomatik tespit etmek güvenilir DEĞİL: bir ifadenin
#: kullanıcı verisi mi etiket mi olduğu kaynağına bakmadan bilinemez. Bu
#: liste o yüzden TAHMİN değil SÖZLEŞME: buradaki adlardan okunan bir değer
#: `trf` parametresine girerken `tr()` ile sarılmak zorundadır ve
#: `tests/test_i18n_static_gate.py` bunu kapıya bağlar.
#:
#: KAPSAM DAR VE ÖLÇÜLÜ. Bir girdi ancak GERÇEKTEN bir `trf`/`_tf` KEYWORD
#: parametresinde okunuyorsa burada durur; kapı bunu AST ile ölçer ve ölü
#: girdiyi reddeder. Metin üretimi saf yardımcılara (`asset_type_button_text`,
#: `gold_type_button_text`, `balance_detail_text` …) taşındığında bazı adlar
#: artık doğrudan parametreye girmiyor — onlar listeden ÇIKARILDI:
#:
#:   `_asset_selected_type`, `_GOLD_TYPES`  -> yardımcıya argüman olarak
#:       geçiyorlar; yardımcının kendi parametresi (`asset_type`, `label`)
#:       şablona giriyor. `asset_type` listede; `label` BİLEREK değil —
#:       fazla genel bir ad, yanlış pozitif üretirdi. O yardımcıların
#:       `_t()` davranışı gerçek üretim-yolu testleriyle korunuyor
#:       (tests/test_i18n_controlled_values.py).
#:   `ACCOUNT_TYPE_LABELS`                  -> önce yerel `label`e alınıp
#:       `label=_t(label)` olarak veriliyor; aynı gerekçe.
#:   `MONTHS`, `_MONTH_KEYS`, `_WEEKDAY_NAMES` -> düz `_t(...)` çağrılarında
#:       kullanılıyorlar, şablon parametresinde değil. `tr()` sarmaları
#:       yerinde; bu sözleşmenin konusu değiller.
CONTROLLED_LABEL_SOURCES = frozenset({
    # Varlık türü — `asset_type_button_text` / `asset_type_short_text`
    # yardımcılarının parametresi doğrudan şablona giriyor.
    "asset_type",
    # Defter kaynak etiketleri (mixins/history_mixin.py::ledger_source_text).
    "_SOURCE_LABELS",
    # Abonelik sıklığı (mixins/insights_mixin.py::recurring_candidate_title).
    "_frequency_label",
    # Takvim başlığındaki ay adı (mixins/calendar_mixin.py).
    "_MONTH_NAMES",
})


#: KULLANICININ KENDİ YAZDIĞI alanlar — hiçbir koşulda çevrilmez.
#:
#: `CONTROLLED_LABEL_SOURCES`in karşı tarafı. Bu adlardan okunan bir değer
#: çeviri fonksiyonuna geçirilemez (kapı: `tests/test_i18n_static_gate.py`)
#: ve envanterde ayrı bir sınıf olarak raporlanır.
#:
#: `type_label`, `category`, `asset_type` BURADA DEĞİL: onlar uygulamanın
#: kendi etiket sözlüğü, kullanıcının serbest metni değil.
USER_DATA_FIELDS = frozenset({
    "name",
    "goal_name",
    "debt_name",
    "account_name",
    "card_name",
    "asset_name",
    "description",
})


def escape_markup(text) -> str:
    """Kullanıcı verisini Kivy markup'ına GİRMEDEN önce zararsızlaştırır.

    Kivy'nin `escape_markup`u ile BİREBİR aynı dönüşüm (`&` önce, sonra `[`
    ve `]`), ama bu modül Kivy'ye bağımlı olmadan çalışabilsin diye burada.
    Sıra önemlidir: `&` sonra kaçışlansaydı kendi ürettiğimiz `&bl;`
    dizilerini de bozardık.

    NEDEN: hesap/kart adı gibi kullanıcı verisi `markup=True` etiketlere
    giriyor. Ham geçtiğinde `[color=...]` yazan bir ad arayüzü biçimlendirir;
    bu, düzeltilen çeviri kusurunun kardeşi olan bir "kullanıcı verisi
    yorumlanıyor" kusurudur.
    """
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("[", "&bl;")
        .replace("]", "&br;")
    )


def placeholders(template: str) -> frozenset:
    """Şablondaki yer tutucu adları. Sözlük tutarlılığı kapısı bunu kullanır."""
    return frozenset(_PLACEHOLDER.findall(template or ""))


class TranslationTemplateError(ValueError):
    """Şablon ile verilen parametreler uyuşmuyor — GELİŞTİRİCİ hatası.

    Veriye değil KODA bağlı olduğu için üretimde ilk kez ortaya çıkması
    mümkün değil: `tests/test_i18n_static_gate.py` kod tabanındaki her `trf`
    şablonunu render ediyor.
    """


def trf(template: str, language: str | None = None, **params) -> str:
    """ÖNCE şablonu çevirir, SONRA parametreleri yerleştirir.

    Sıra sözleşmenin kendisi: parametreler çeviriden SONRA girdiği için
    kullanıcı verisi çeviri motoruna hiç uğramaz.

    Yerleştirme `str.format` ile DEĞİL, dar bir `{ad}` sözleşmesiyle ve TEK
    GEÇİŞTE yapılır. Gerekçe:

      * **Dar sözleşme.** Yalnız `{ad}` biçimindeki yer tutucular tanınır.
        `str.format`ın desteklediği biçim belirteci (`{x:>10}`), öznitelik
        (`{x.attr}`) ve indeks (`{x[0]}`) erişimi ÇEVRİLEBİLİR bir şablonda
        istenmiyor: sayı/tarih/para biçimlendirmesi çağrı yerinde kalmalı ve
        bir çeviri metni nesne grafiğine uzanabilmemeli.
      * **Doğrulanmış yer tutucu kümesi.** Şablonun beklediği adlarla verilen
        parametreler karşılaştırılır; uyuşmazlık `TranslationTemplateError`.
        `str.format` aynı durumda `KeyError`/`IndexError` fırlatır ve hata
        mesajı hangi ŞABLONUN bozuk olduğunu söylemez.
      * **Tek geçiş = öngörülebilirlik.** Bir parametrenin içindeki `{başka}`
        metni ikinci bir parametreyle değiştirilemez; sonuç parametre
        sırasından bağımsızdır.

    DÜZELTME (önceki gerekçe yanlıştı): `str.format` YERLEŞTİRDİĞİ değeri
    yeniden şablon olarak yorumlamaz — `"{x}".format(x="{test}")` sonucu
    `"{test}"`tir, hata değil. Buradaki tercih bir çökme korkusuna değil,
    yukarıdaki üç özelliğe dayanıyor.

    Değerler hiçbir işleme girmediği için yüzde işareti, süslü parantez,
    emoji, satır sonu ve RTL karakterleri birebir korunur.
    """
    if template is None:
        return ""
    translated = tr(template, language)

    expected = placeholders(translated)
    supplied = frozenset(params)
    if expected != supplied:
        missing = sorted(expected - supplied)
        extra = sorted(supplied - expected)
        raise TranslationTemplateError(
            f"şablon parametreleri uyuşmuyor: eksik={missing} fazla={extra} "
            f"şablon={template!r}"
        )

    values = {key: "" if value is None else str(value)
              for key, value in params.items()}
    return _PLACEHOLDER.sub(lambda match: values[match.group(1)], translated)
