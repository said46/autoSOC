// make hidden input visible
let CRN_input = document.getElementById("CurrentRoleName");
CRN_input.style.display = "inline-block";

let dd = $('#CurrentRoleName').data('kendoDropDownList');
let ds = dd.dataSource;
console.log(ds.data);

// Get all data as JSON string
let jsonString = JSON.stringify(ds.data());
console.log(jsonString);

// Get as formatted JSON string
let jsonData = JSON.stringify(ds.data(), null, 2);

// add an item
ds.add({
    Text: 'Хрен моржовый',
    Value: 'DD',
    Selected: false
});

const roleData = [
  {
    "Text": "Руководитель участка",
    "Value": "AA",
    "Selected": false
  },
  {
    "Text": "Руководитель работ",
    "Value": "PA",
    "Selected": false
  },
  {
    "Text": "Руководитель объекта",
    "Value": "SC",
    "Selected": false
  },
  {
    "Text": "Уполномоченный по механической изоляции",
    "Value": "IAM",
    "Selected": false
  },
  {
    "Text": "Уполномоченный по технологической изоляции",
    "Value": "IAP",
    "Selected": false
  },
  {
    "Text": "Уполномоченный по изоляции систем управления",
    "Value": "IAC",
    "Selected": false
  },
  {
    "Text": "Уполномоченный по изоляции систем безопасности",
    "Value": "IAS",
    "Selected": false
  },
  {
    "Text": "Уполномоченный по изоляции электрических систем",
    "Value": "IAE",
    "Selected": false
  },
  {
    "Text": "Руководитель деятельности",
    "Value": "OA",
    "Selected": false
  },
  {
    "Text": "Посетитель",
    "Value": "VS",
    "Selected": false
  },
  {
    "Text": "Ответственный за электрохозяйство",
    "Value": "RPE",
    "Selected": false
  },
  {
    "Text": "Оператор ЦПУ",
    "Value": "CRO",
    "Selected": false
  },
  {
    "Text": "Исполняющий форсирование",
    "Value": "OAC",
    "Selected": false
  },
  {
    "Text": "Проверяющий форсирование",
    "Value": "OAV",
    "Selected": false
  }
];