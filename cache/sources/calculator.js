(function () {
  'use strict';
  function calculate(v) {
    const keys = ['rate','hit','cache','source','fill','background','budget'];
    if (!keys.every(k => Number.isFinite(v[k])) || v.rate < 0 || v.hit < 0 || v.hit > 100 ||
        v.cache < 0 || v.source <= 0 || v.fill < 0 || v.background < 0 || v.budget < 0) return null;
    const h = v.hit / 100;
    const load = v.rate * (1-h) + v.background;
    const mean = v.cache + (1-h)*(v.source+v.fill);
    const threshold = (v.cache+v.fill)/(v.source+v.fill)*100;
    const required = v.rate === 0 ? null : Math.max(0, (1-(v.budget-v.background)/v.rate)*100);
    return {load,mean,threshold,required,concurrency:v.rate*mean/1000,within:load <= v.budget};
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {calculate};
  if (typeof document === 'undefined') return;
  const root = document.querySelector('[data-cache-calculator]');
  if (!root) return;
  const fields = [
    ['rate','Чтения приложения, запросов/с',20000],['hit','Попадания, %',95],
    ['cache','Проверка кэша C, мс',0.6],['source','Источник D, мс',8],
    ['fill','Ожидаемое заполнение F, мс',0.4],
    ['background','Прочие чтения и фон, запросов/с',500],
    ['budget','Допустимый поток источника, запросов/с',3000]
  ];
  root.className='interactive cache-calculator';
  root.innerHTML='<h3>Рассчитать задержку и ресурс источника</h3><p>Учебная последовательная модель: один промах — одно чтение. Стоимости постоянны, очередь и повторы не моделируются. Результат не является p99.</p><div class="calc-fields">'+fields.map(([key,label,value])=>'<label for="calc-'+key+'">'+label+'<input id="calc-'+key+'" data-calc="'+key+'" type="number" step="any" min="0" '+(key==='hit'?'max="100" ':'')+'value="'+value+'"></label>').join('')+'</div><output aria-live="polite"></output>';
  function render(){
    const v={}; root.querySelectorAll('input').forEach(el=>v[el.dataset.calc]=el.value.trim()===''?NaN:Number(el.value));
    const r=calculate(v), out=root.querySelector('output');
    if(!r){out.textContent='Введите конечные неотрицательные числа. Попадания: от 0 до 100%; время источника должно быть больше нуля.';return;}
    const n=x=>x.toLocaleString('ru-RU',{maximumFractionDigits:3});
    const need=r.required===null?'Нет основного потока: сравните фон с бюджетом.':r.required>100?'Даже 100% попаданий недостаточно: фон превышает бюджет.':'Минимум попаданий по бюджету: '+n(r.required)+'%.';
    out.textContent='Среднее время: '+n(r.mean)+' мс. Источник: '+n(r.load)+' запросов/с — '+(r.within?'в пределах бюджета. ':'бюджет превышен. ')+need+' Порог улучшения среднего: h > '+n(r.threshold)+'%. Средняя конкуренция λW: '+n(r.concurrency)+'.';
  }
  root.addEventListener('input',render);render();
})();
