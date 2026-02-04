import os

card_html = '''
<div class="product-card" style="background-color:#1a1a1a;color:#fff;border-radius:12px;overflow:hidden;max-width:550px;display:flex;box-shadow:0 10px 30px rgba(0,0,0,0.7);font-family:'Segoe UI',Tahoma,Geneva,Verdana,sans-serif">
    <div style="flex:0 0 180px;display:flex;align-items:center;justify-content:center;background:#222">
        <img src="{icon}" alt="{title}" style="width:100%;height:auto;object-fit:cover">
    </div>
    <div style="padding:20px;flex:1">
        <div style="display:flex;align-items:center;font-size:14px;color:#aaa;margin-bottom:12px">
            совпадение {match}% 
            <span class="hint-trigger" style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border:1px solid #fff;border-radius:50%;margin-left:8px;cursor:pointer;font-weight:bold;background:transparent;color:#fff;transition:all 0.2s" onmouseover="showHint(event)" onmouseout="hideHint(event)" onclick="toggleHint(event)">
                ?
            </span>
        </div>
        <h2 style="font-size:22px;margin:5px 0 15px;font-weight:600">{title}</h2>
        <div style="display:flex;align-items:center;margin:15px 0">
            <button onclick="updateQty(this,-1)" style="background:#333;border:none;color:#fff;width:36px;height:36px;border-radius:8px;cursor:pointer;font-size:20px;display:flex;align-items:center;justify-content:center;transition:background 0.2s">−</button>
            <span class="qty-display" style="margin:0 12px;font-size:18px;min-width:24px;text-align:center">1</span>
            <button onclick="updateQty(this,1)" style="background:#333;border:none;color:#fff;width:36px;height:36px;border-radius:8px;cursor:pointer;font-size:20px;display:flex;align-items:center;justify-content:center;transition:background 0.2s">+</button>
        </div>
        <div style="font-size:24px;font-weight:bold;margin:10px 0">{cost} p.</div>
        <a href="#" style="color:#4da6ff;text-decoration:none;font-size:16px;display:block;margin:8px 0;transition:opacity 0.2s">Нужны другие размеры?</a>
        <p style="color:#aaa;font-size:14px;line-height:1.5">lottahome.ru поможет изготовить мебель под другие размеры.</p>
    </div>
    
    <div class="hint-modal" style="display:none;position:fixed;top:0;left:0;width:100%;height:100%;background-color:rgba(0,0,0,0.85);justify-content:center;align-items:center;z-index:1000;padding:20px">
        <div style="background-color:#2d2d2d;padding:28px;border-radius:12px;max-width:90%;position:relative;border:1px solid #444;box-shadow:0 0 30px rgba(0,0,0,0.9);color:#ddd">
            <span onclick="closeHint(this)" style="position:absolute;top:15px;right:15px;font-size:24px;cursor:pointer;color:#aaa;transition:color 0.2s">&times;</span>
            <h3 style="color:#4da6ff;margin-bottom:15px;font-size:22px">Совпадение</h3>
            <p style="line-height:1.6;margin-bottom:12px">Это означает, на сколько мебель подходит под Ваш интерьер (по размерам, стилю, цвету и т.д.)</p>
            <p style="line-height:1.6;margin-bottom:12px">Нужны эта мебель, но с другим оформлением?</p>
            <p style="line-height:1.6">lottahome.ru поможет изготовить мебель на заказ.</p>
        </div>
    </div>
</div>

<script>
function showHint(e) {
    const modal = e.target.closest('.product-card').querySelector('.hint-modal');
    window.hintTimeout = setTimeout(() => {
        modal.style.display = 'flex';
    }, 500);
    e.target.style.backgroundColor = '#fff';
    e.target.style.color = '#1a1a1a';
}

function hideHint(e) {
    clearTimeout(window.hintTimeout);
    e.target.style.backgroundColor = 'transparent';
    e.target.style.color = '#fff';
}

function toggleHint(e) {
    e.stopPropagation();
    const modal = e.target.closest('.product-card').querySelector('.hint-modal');
    modal.style.display = modal.style.display === 'flex' ? 'none' : 'flex';
}

function closeHint(el) {
    el.closest('.hint-modal').style.display = 'none';
}

function updateQty(btn, delta) {
    const qtyEl = btn.closest('.product-card').querySelector('.qty-display');
    let qty = parseInt(qtyEl.textContent);
    qty = Math.max(1, qty + delta);
    qtyEl.textContent = qty;
}

document.addEventListener('click', function(e) {
    if (e.target.classList.contains('hint-modal')) {
        e.target.style.display = 'none';
    }
});

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        document.querySelectorAll('.hint-modal').forEach(m => m.style.display = 'none');
    }
});
</script>
'''

class Card:
    def __init__(self, json_object):
        self.match = json_object["match"]
        self.icon = json_object["icon"]
        self.title = json_object["title"]
        self.cost = json_object["cost"]
    
    def render(self):
        return card_html.format(
            match=self.match,
            icon=self.icon,
            title=self.title,
            cost=self.cost
        )

class CardList:
    def __init__(self, json):
        self.cards = []
        for obj in json["cards"]:
            card = Card(obj)
            self.cards.append(card)
    
    def render_all(self):
        return '\n'.join([card.render() for card in self.cards])