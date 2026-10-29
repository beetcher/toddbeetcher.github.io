const {chromium}=require('/Users/nddev/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8772/');
 await page.waitForFunction(()=>Array.from(document.images).every(i=>i.complete&&i.naturalWidth>0));
 const imageCount=await page.locator('img').count();
 await page.screenshot({path:'creative-review-2026-10-27/qa/desktop-review.png',fullPage:true});
 const widths=[];
 for(const width of [320,390,768,1440]){await page.setViewportSize({width,height:844});widths.push({width,overflow:await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)});}
 await page.setViewportSize({width:390,height:844});await page.locator('#ready').scrollIntoViewIfNeeded();
 await page.screenshot({path:'creative-review-2026-10-27/qa/ready-start-390.png',fullPage:false});
 await page.locator('#next').click();if(!await page.locator('#question-error').innerText())throw Error('Missing validation');
 async function choose(value){await page.locator(`input[value="${value}"]`).check();await page.locator('#next').click();}
 const paths={begin:'Start with one task you can check.',notice:'Practice recognizing the moment.',judgment:'Make checking part of the task.',workflow:'Choose a useful piece of real work.'};
 const results=[];
 for(const [route,title]of Object.entries(paths)){
 await page.locator('#restart').click();await choose('organization');await choose('occasional');await choose(route);
 await page.locator('input[value="work"]').check();await page.locator('#task').fill('<img src=x onerror=alert(1)>');
 await page.locator('#back').click();await page.locator('#next').click();if(await page.locator('#task').inputValue()!=='<img src=x onerror=alert(1)>')throw Error('Task lost on back');
 await page.locator('#next').click();await choose('workshop');
 const actual=await page.locator('#result-title').innerText();if(actual!==title)throw Error('Wrong route');
 const brief=await page.locator('#brief-text').inputValue();if(!brief.includes('<img src=x onerror=alert(1)>'))throw Error('Brief missing task');
 if(await page.locator('img').count()!==3)throw Error('Unsafe insertion');
 results.push({route,title:actual,link:await page.locator('#artifact-link').getAttribute('href')});
 }
 await page.locator('#handoff-button').click();if(!await page.locator('#handoff').isVisible())throw Error('Handoff missing');
 await page.evaluate(()=>Object.defineProperty(navigator,'clipboard',{value:{writeText:async()=>{throw Error('test denied')}},configurable:true}));
 await page.locator('#copy-brief').click();if(!(await page.locator('#copy-status').innerText()).includes('Select and copy'))throw Error('Copy fallback failed');
 await page.locator('#result-view').scrollIntoViewIfNeeded();await page.screenshot({path:'creative-review-2026-10-27/qa/ready-result-390.png',fullPage:false});
 await page.locator('#restart').click();if(await page.locator('input:checked').count()!==0)throw Error('Reset failed');
 await page.reload();if(await page.locator('input:checked').count()!==0)throw Error('Unexpected persistence');
 const result={imageCount,widths,results,errors,checks:['required answer','four result routes','back preserves task','safe text insertion','handoff preview','copy fallback','reset','reload clears']};
 fs.writeFileSync('creative-review-2026-10-27/qa/check-results.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));await browser.close();
})();
